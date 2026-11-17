# Entrenador de Ventas

Simulador de conversaciones para entrenar a los representantes de zona de la automotriz.
El agente interpreta al dueño de un concesionario; el representante practica la reunión y,
al terminar, recibe una devolución con puntaje por criterio.

- Dos focos: **Ventas** y **Posventa**.
- Dos países: **Argentina** (español) y **Brasil** (portugués). El dueño habla en el idioma elegido.

## Cómo usarlo

1. Copiar `.env.ejemplo` como `.env` y completar `ANTHROPIC_API_KEY`.
2. Iniciar el servidor desde esta carpeta:

   ```
   .venv\Scripts\python.exe -m uvicorn app.servidor:app --port 8010
   ```

3. Abrir http://localhost:8010 en el navegador.

Primera vez en otra máquina: `py -m venv .venv` y `.venv\Scripts\python.exe -m pip install -r requirements.txt`.

## Cómo "entrenar" al agente

No se reentrena ningún modelo: se editan fichas de texto.

- **Escenarios**: un archivo `.yaml` por conversación típica en `escenarios/ventas/` o
  `escenarios/posventa/`. Para sumar uno, copiar una ficha existente, cambiar el `id` y
  completar perfil del dueño, situación, objeciones, qué lo mueve y hasta dónde cede.
  Los cuatro incluidos son ejemplos para reemplazar con casos reales. Se leen al recargar la página.
- **Criterios de evaluación**: `config/criterios.yaml`.
- **Conversaciones hechas**: cada práctica queda guardada en `datos/sesiones/` (transcripción
  y devolución). Sirven para revisar cómo actúa el dueño y ajustar las fichas.

## Compartirlo con un tester externo (Railway)

1. Subir esta carpeta a un repositorio **privado** de GitHub. El archivo `.env` y la carpeta
   `datos` quedan afuera solos.
2. En Railway, crear un proyecto desde ese repositorio (**New Project > Deploy from GitHub repo**).
   El archivo `Procfile` indica el comando de inicio.
3. En **Variables**, cargar:
   - `ANTHROPIC_API_KEY`: la clave de Anthropic.
   - `CODIGO_ACCESO`: una frase que solo conozcan los testers. Sin esta variable cualquiera
     con el enlace puede usar la aplicación y consumir saldo de la clave.
   - `DATOS_DIR=/data`
4. Agregar un **Volume** montado en `/data`. Ahí quedan las conversaciones de los testers
   entre reinicios.
5. En **Settings > Networking**, elegir **Generate Domain**. Esa dirección y el código de
   acceso son lo que se le pasa al tester.

Para cortar el acceso, cambiar `CODIGO_ACCESO` o borrar el dominio. Conviene además fijar un
límite de gasto mensual en la consola de Anthropic.

## Estructura

- `app/simulador.py`: instrucciones del personaje, llamada a Claude y evaluación.
- `app/servidor.py`: servidor web y sesiones.
- `web/index.html`: pantalla de chat.

## Próximas fases

1. Voz con ElevenLabs: una voz por país (variables ya previstas en `.env.ejemplo`) y micrófono.
2. Avatar con cara ficticia sincronizado con la voz.
