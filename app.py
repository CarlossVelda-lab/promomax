import re
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style='whitegrid')

COLUMN_MAP = {
    'precio': ['precio', 'price', 'precio_unitario', 'precio unitario', 'valor unitario', 'unit price'],
    'costo': ['costo', 'cost', 'costo_unitario', 'costo unitario', 'cost_unit', 'cost unit'],
    'sku': ['sku', 'id', 'id_producto', 'producto_id', 'product_id', 'product', 'codigo', 'codigo_producto'],
    'ventas': ['ventas', 'sales', 'ingresos', 'revenue', 'monto', 'valor'],
    'cantidad_vendida': ['cantidad', 'cantidad_vendida', 'unidades', 'qty', 'quantity', 'cantidad vendida', 'units'],
    'categoria': ['categoria', 'category', 'categoría', 'segmento'],
    'region': ['region', 'región', 'territorio', 'area'],
    'fecha': ['fecha', 'date', 'fecha_venta', 'fecha venta', 'sale_date', 'fecha de venta', 'date_venta'],
    'fecha_inicio': ['fecha_inicio', 'fecha_inicio_promocion', 'fecha inicio', 'start_date', 'inicio', 'fecha_inicio_promo'],
    'fecha_fin': ['fecha_fin', 'fecha_fin_promocion', 'fecha fin', 'end_date', 'fin', 'fecha_final', 'fecha final'],
    'descuento': ['descuento', 'discount', 'promo', 'promocion', 'promoción', 'con_descuento', 'tiene_descuento']
}

EXPECTED_SALES = ['precio', 'costo', 'sku', 'ventas', 'cantidad_vendida', 'categoria', 'region', 'fecha', 'descuento']
EXPECTED_PROMOS = ['sku', 'fecha_inicio', 'fecha_fin', 'descuento']


def clean_column_name(name):
    if name is None:
        return ''
    return re.sub(r'[^a-z0-9]', '', str(name).strip().lower())


def map_columns(columns, expected):
    mapped = {}
    flat = {clean_column_name(alias): key for key, aliases in COLUMN_MAP.items() for alias in aliases}
    for col in columns:
        ccol = clean_column_name(col)
        if ccol in flat:
            mapped[col] = flat[ccol]
            continue
        for alias, key in flat.items():
            if alias in ccol and alias:
                mapped[col] = key
                break
    if expected is None:
        return mapped
    result = {}
    for column in columns:
        if column in mapped:
            result[column] = mapped[column]
    return result


def load_file(uploaded_file):
    if uploaded_file is None:
        return None
    if uploaded_file.name.lower().endswith(('.xls', '.xlsx')):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def normalize_discount(series):
    if series is None:
        return None
    values = series.astype(str).str.lower().str.strip()
    values = values.replace({'true': '1', 'false': '0', 'si': '1', 'sí': '1', 'no': '0', 'yes': '1', 'y': '1', 'n': '0'})
    numeric = pd.to_numeric(values.str.replace('%', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')
    result = pd.Series(np.where(numeric.notna() & numeric > 0, 1, np.where(numeric == 0, 0, np.nan)), index=series.index)
    result = result.fillna(values.map({'1': 1, '0': 0}))
    result = result.fillna(np.where(values.str.contains('desc|promo|discount|rebaja', na=False), 1, np.where(values.str.contains('sin|no|none|0', na=False), 0, np.nan)))
    return result.astype('Int64')


def standardize_dataframe(df, expected_keys, file_label):
    if df is None:
        return None, []
    columns = list(df.columns)
    mapping = map_columns(columns, expected_keys)
    df = df.rename(columns=mapping)
    missing = [key for key in expected_keys if key not in df.columns]
    return df, missing


def parse_dates(df, columns):
    for col in columns:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
            except Exception:
                df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def compute_revenue(df):
    if 'ventas' not in df.columns and {'precio', 'cantidad_vendida'}.issubset(df.columns):
        df['ventas'] = df['precio'] * df['cantidad_vendida']
    return df


def compute_margin(df):
    if {'precio', 'costo'}.issubset(df.columns):
        df['margen'] = df['precio'] - df['costo']
    return df


def add_discount_flag(sales, promos):
    if 'descuento' in sales.columns:
        sales['descuento_flag'] = normalize_discount(sales['descuento']).fillna(0).astype(int)
    else:
        sales['descuento_flag'] = 0
    if promos is not None and 'sku' in sales.columns and 'sku' in promos.columns:
        promo_lookup = promos[['sku', 'fecha_inicio', 'fecha_fin']].dropna(subset=['sku']).copy()
        sales = sales.merge(promo_lookup, on='sku', how='left', suffixes=('', '_promo'))
        if 'fecha_inicio' in sales.columns and 'fecha_fin' in sales.columns:
            in_promo = (sales['fecha'] >= sales['fecha_inicio']) & (sales['fecha'] <= sales['fecha_fin'])
            sales['descuento_flag'] = np.where(in_promo, 1, sales['descuento_flag'])
    sales['descuento_flag'] = sales['descuento_flag'].fillna(0).astype(int)
    return sales


def label_period(sales):
    sales['periodo'] = 'sin promo'
    if 'fecha_inicio' in sales.columns and 'fecha_fin' in sales.columns:
        before = sales['fecha'] < sales['fecha_inicio']
        during = (sales['fecha'] >= sales['fecha_inicio']) & (sales['fecha'] <= sales['fecha_fin'])
        after = sales['fecha'] > sales['fecha_fin']
        sales.loc[before, 'periodo'] = 'antes'
        sales.loc[during, 'periodo'] = 'durante'
        sales.loc[after, 'periodo'] = 'después'
    return sales


def build_month(sales):
    if 'fecha' in sales.columns:
        sales['mes'] = sales['fecha'].dt.to_period('M').dt.to_timestamp()
    else:
        sales['mes'] = pd.NaT
    return sales


def plot_bar(data, x, y, title, xlabel=None, ylabel=None, hue=None):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=data, x=x, y=y, hue=hue, ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel or x)
    ax.set_ylabel(ylabel or y)
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig


def plot_line(data, x, y, title, xlabel=None, ylabel=None, hue=None):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    sns.lineplot(data=data, x=x, y=y, hue=hue, marker='o', ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel or x)
    ax.set_ylabel(ylabel or y)
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig


def generate_insights(sales):
    count_discount = int(sales['descuento_flag'].sum())
    total_sales = len(sales)
    pct_discount = 100 * count_discount / max(total_sales, 1)
    avg_revenue_disc = sales.loc[sales['descuento_flag'] == 1, 'ventas'].mean()
    avg_revenue_no = sales.loc[sales['descuento_flag'] == 0, 'ventas'].mean()
    avg_margin_disc = sales.loc[sales['descuento_flag'] == 1, 'margen'].mean()
    avg_margin_no = sales.loc[sales['descuento_flag'] == 0, 'margen'].mean()
    months = sales.dropna(subset=['mes']).copy()
    trend = months.groupby(['mes', 'descuento_flag'])['ventas'].mean().reset_index()
    conclusion = []

    conclusion.append(f"Se procesaron {total_sales} ventas; {count_discount} registros ({pct_discount:.1f}%) tienen descuento.")
    if not np.isnan(avg_revenue_disc) and not np.isnan(avg_revenue_no):
        diff = avg_revenue_disc - avg_revenue_no
        conclusion.append(
            f"El ingreso promedio con descuento es {'mayor' if diff > 0 else 'menor'} en {abs(diff):.2f} unidades monetarias frente a las ventas sin descuento.")
    if not np.isnan(avg_margin_disc) and not np.isnan(avg_margin_no):
        diff_m = avg_margin_disc - avg_margin_no
        conclusion.append(
            f"El margen promedio {'mejora' if diff_m > 0 else 'disminuye'} {'en' if diff_m > 0 else 'en'} {abs(diff_m):.2f} unidades monetarias cuando hay descuento.")
    if trend.shape[0] > 0:
        latest = trend.sort_values('mes').groupby('descuento_flag').last().reset_index()
        if len(latest) == 2:
            conclusion.append(
                "Las tendencias mensuales muestran la comparación entre grupos con y sin descuento, lo que permite evaluar el efecto temporal de promociones.")
    conclusion.append("Este análisis se realizó localmente en el navegador usando un motor de insights basado en reglas, sin depender de APIs externas.")

    return "\n\n".join(conclusion)


def show_instructions():
    st.markdown("## Instrucciones de uso")
    st.markdown(
        "- Carga dos archivos: uno con **ventas** y otro con **promociones**.\n"
        "- Los archivos pueden ser `CSV` o `Excel`.\n"
        "- Ambos archivos deben incluir una columna de **SKU o ID de producto** para relacionarlos.\n"
        "- El archivo de ventas debe incluir columnas de **precio**, **costo**, **ventas** o **cantidad vendida**, **categoría**, **región**, **fecha** y **descuento**.\n"
        "- El archivo de promociones debe incluir columnas de **SKU**, **fecha de inicio**, **fecha fin** y **descuento** o indicador de promoción.\n"
        "- Si no existe una columna de ingresos, el sistema calculará `precio * cantidad vendida`.\n"
        "- El valor de descuento se normaliza a `1` si hay promoción/ descuento y a `0` si no la hay."
    )
    st.markdown("---")


def main():
    st.title("Efecto de promociones")
    st.write("Carga tus archivos de ventas y promociones para analizar el impacto de descuentos con gráficos y conclusiones locales.")
    show_instructions()

    sales_file = st.file_uploader("Carga el archivo de ventas", type=['csv', 'xls', 'xlsx'], key='sales')
    promo_file = st.file_uploader("Carga el archivo de promociones", type=['csv', 'xls', 'xlsx'], key='promos')

    sales_df = load_file(sales_file)
    promos_df = load_file(promo_file)

    if sales_df is None or promos_df is None:
        st.warning("Carga ambos archivos para generar el análisis completo.")
        return

    sales_df, missing_sales = standardize_dataframe(sales_df, EXPECTED_SALES, 'ventas')
    promos_df, missing_promos = standardize_dataframe(promos_df, EXPECTED_PROMOS, 'promociones')

    st.subheader("Revisión de columnas detectadas")
    st.write("Columnas del archivo de ventas:")
    st.write(list(sales_df.columns))
    st.write("Columnas del archivo de promociones:")
    st.write(list(promos_df.columns))

    if missing_sales:
        st.error(f"Faltan columnas clave en ventas: {', '.join(missing_sales)}")
    if missing_promos:
        st.error(f"Faltan columnas clave en promociones: {', '.join(missing_promos)}")

    sales_df = parse_dates(sales_df, ['fecha'])
    promos_df = parse_dates(promos_df, ['fecha_inicio', 'fecha_fin', 'fecha'])

    sales_df = compute_revenue(sales_df)
    sales_df = compute_margin(sales_df)
    sales_df = add_discount_flag(sales_df, promos_df)
    sales_df = label_period(sales_df)
    sales_df = build_month(sales_df)

    st.subheader("Vista previa de datos de ventas")
    st.dataframe(sales_df.head(10))

    metrics = {
        'ventas_descuento': sales_df.loc[sales_df['descuento_flag'] == 1, 'ventas'].sum(),
        'ventas_sin_descuento': sales_df.loc[sales_df['descuento_flag'] == 0, 'ventas'].sum(),
        'unidades_descuento': sales_df.loc[sales_df['descuento_flag'] == 1, 'cantidad_vendida'].sum() if 'cantidad_vendida' in sales_df.columns else np.nan,
        'unidades_sin_descuento': sales_df.loc[sales_df['descuento_flag'] == 0, 'cantidad_vendida'].sum() if 'cantidad_vendida' in sales_df.columns else np.nan,
    }

    st.markdown("---")
    st.subheader("Gráficas de comparación")

    if 'ventas' in sales_df.columns and 'descuento_flag' in sales_df.columns:
        avg_rev = sales_df.groupby('descuento_flag', observed=True)['ventas'].mean().reset_index()
        avg_rev['descuento_flag'] = avg_rev['descuento_flag'].map({0: 'Sin descuento', 1: 'Con descuento'})
        fig1 = plot_bar(avg_rev, 'descuento_flag', 'ventas', 'Promedio de ingresos por producto con vs. sin descuento', xlabel='Grupo', ylabel='Ingreso promedio')
        st.pyplot(fig1)

    if 'margen' in sales_df.columns and 'descuento_flag' in sales_df.columns:
        avg_margin = sales_df.groupby('descuento_flag', observed=True)['margen'].mean().reset_index()
        avg_margin['descuento_flag'] = avg_margin['descuento_flag'].map({0: 'Sin descuento', 1: 'Con descuento'})
        fig2 = plot_bar(avg_margin, 'descuento_flag', 'margen', 'Margen promedio en productos tratados vs no tratados', xlabel='Grupo', ylabel='Margen promedio')
        st.pyplot(fig2)

    if 'mes' in sales_df.columns and 'cantidad_vendida' in sales_df.columns:
        units_month = sales_df.groupby(['mes', 'descuento_flag'], observed=True)['cantidad_vendida'].sum().reset_index()
        units_month['descuento_flag'] = units_month['descuento_flag'].map({0: 'Sin descuento', 1: 'Con descuento'})
        fig3 = plot_line(units_month, 'mes', 'cantidad_vendida', 'Cantidad total de unidades vendidas con descuento vs sin descuento (por mes)', xlabel='Mes', ylabel='Unidades vendidas', hue='descuento_flag')
        st.pyplot(fig3)

    if 'mes' in sales_df.columns and 'ventas' in sales_df.columns:
        avg_month = sales_df.groupby(['mes', 'descuento_flag'], observed=True)['ventas'].mean().reset_index()
        avg_month['descuento_flag'] = avg_month['descuento_flag'].map({0: 'Sin descuento', 1: 'Con descuento'})
        fig4 = plot_line(avg_month, 'mes', 'ventas', 'Evolución mensual de ventas promedio en ambos grupos', xlabel='Mes', ylabel='Ventas promedio', hue='descuento_flag')
        st.pyplot(fig4)

    st.markdown("---")
    st.subheader("Conclusión y insights generados localmente")
    conclusion_text = generate_insights(sales_df)
    st.write(conclusion_text)

    st.markdown("---")
    st.write("Aplicación creada para analizar promociones sin utilizar APIs externas de LLM. Los insights se generan en tiempo real con los datos cargados.")


if __name__ == '__main__':
    main()
