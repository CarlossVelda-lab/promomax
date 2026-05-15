# Efecto de promociones

Aplicación de análisis de promociones y descuentos usando Streamlit.

## Descripción

Esta página web permite:

- Cargar dos archivos: uno de **ventas** y otro de **promociones**.
- Aceptar archivos `CSV` o `Excel`.
- Normalizar columnas clave como `precio`, `costo`, `sku`, `ventas`, `cantidad vendida`, `categoría`, `región`, `fecha`, `descuento`.
- Convertir la información de descuento a un valor binario local: `1` si hay descuento y `0` si no hay descuento.
- Generar gráficos de comparación en tiempo real:
  - Promedio de ingresos por producto con vs. sin descuento.
  - Margen promedio en productos tratados vs. no tratados.
  - Cantidad total de unidades vendidas con descuento vs. sin descuento por mes.
  - Evolución mensual de ventas promedio en ambos grupos.
- Presentar una conclusión local generada sin depender de APIs externas.

## Uso

1. Instala dependencias:

```bash
pip install -r requirements.txt
```

2. Ejecuta la aplicación:

```bash
streamlit run app.py
```

3. Abre la URL que Streamlit muestre en tu navegador.

## Repositorio

https://github.com/CarlossVelda-lab/tarea-1
