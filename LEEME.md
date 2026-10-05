# Agenda de Asturias en RSS

`generar_rss.py` lee la agenda de turismoasturias.es (portada y todas las categorías)
y genera `agenda-asturias.xml`. GitHub lo ejecuta solo cada 3 horas.

## URL para News Explorer

    https://raw.githubusercontent.com/eurowebmedia/agenda-asturias-rss/main/agenda-asturias.xml

## Cómo funciona

- Cada evento sale una sola vez, aunque esté en varias categorías.
- La fecha del elemento en el feed es la del día en que apareció en la agenda,
  así los eventos nuevos salen arriba en News Explorer.
- Cada entrada lleva foto, fechas, hora, concejo y resumen, y enlaza a la ficha oficial.
- Si la web falla o no devuelve eventos, no se toca el feed anterior.
- Para lanzarlo a mano: pestaña Actions → Actualizar agenda RSS → Run workflow.
