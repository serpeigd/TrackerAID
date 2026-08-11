# Prompt para Lovable — sección "antes/después" de la landing

Adaptado del patrón visual de "FreedomSection" (motionsites.ai): dos
columnas de tarjetas alrededor de un círculo central, sin dependencias
externas (nada de `hls.js`, sin URLs de Mux/Webflow ajenas, sin fuentes de
terceros — usa la tipografía y el sistema de i18n que ya tiene el proyecto).

```
Añade una sección "AntesDespues" a la landing de TrackerAID, después del
hero. Usa el mismo sistema i18n (hook useI18n / t()) y el mismo estilo
Tailwind que ya tiene el resto de la app — no cargues fuentes nuevas ni
dependencias externas.

Layout: en móvil, columna única (icono central arriba, luego las dos
listas apiladas). En desktop (lg+), grid de 3 columnas: lista de "antes"
a la izquierda, círculo con icono en el centro, lista de "después" a la
derecha.

El círculo central es un icono simple (un reloj de arena o una campana,
inline SVG, sin vídeo ni imagen externa) sobre fondo suave.

Cada tarjeta: fondo blanco, sombra sutil, icono de check (✓, verde) o
cruz (✗, gris) a la izquierda del texto. Sin hover, sin animaciones.

Textos ES (clave por defecto) / EN:

Antes / Before:
- ES: "Revisas boletines a mano cada semana, y aun así te dejas convocatorias"
  EN: "You check bulletins by hand every week and still miss calls"
- ES: "No sabes si una ayuda es para tu sector hasta leer las bases enteras"
  EN: "You don't know if a grant fits your sector until reading the full rules"
- ES: "Te enteras de una convocatoria cuando ya casi ha cerrado el plazo"
  EN: "You hear about a grant when the deadline is nearly gone"

Después / After:
- ES: "TrackerAID revisa BDNS por ti cada semana, automáticamente"
  EN: "TrackerAID scans official sources for you, automatically, every week"
- ES: "Solo ves las convocatorias que encajan con tu sector y tu tamaño"
  EN: "You only see calls that match your sector and company size"
- ES: "Recibes el aviso con tiempo de sobra para preparar la solicitud"
  EN: "You get notified with plenty of time to prepare your application"

Título de sección, ES: "De perseguir ayudas a que te encuentren a ti"
Título de sección, EN: "From chasing grants to grants finding you"
```

## Nota sobre el original

El patrón "columnas + círculo central" del prompt original sí es reutilizable
como idea de layout — lo que se descarta es la implementación concreta (HLS,
Mux, fuente de mirror no oficial), no el diseño en sí.
