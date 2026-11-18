# Entrenador de Ventas

Simulador de conversaciones para entrenar a los representantes de zona de la automotriz.
El agente interpreta al dueño de un concesionario; el representante practica la reunión y,
al terminar, recibe una devolución con puntaje por criterio.

- Tres focos: **Ventas**, **Posventa** y **Ventas especiales**.
- Dos países: **Argentina** (español) y **Brasil** (portugués). El dueño habla en el idioma elegido.
- **Concesionario a imitar**: en los escenarios que lo traen, el representante elige un
  concesionario real de la red de su país como referencia. El dueño usa su nombre, su zona y
  lo que ofrece; su personalidad, sus números y sus problemas son ficticios.

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
  Se leen al recargar la página.
- **Banco de escenarios en Excel**: las fichas `V01`–`V06`, `P01`–`P06` y `E01`–`E06` salen
  del Excel de escenarios (hojas «Escenarios IA» y «Referencias AR-BR»). Si el Excel cambia,
  se regeneran con
  `.venv\Scripts\python.exe scripts\importar_excel.py <ruta al .xlsx>`.
  El nombre del dueño, su edad y la traducción al portugués se completan en el script
  (`EXTRA`); un caso nuevo del Excel necesita su fila ahí. Las otras cuatro fichas
  (`stock-y-objetivo`, `inversion-salon`, `capacidad-taller`, `repuestos-originales`) son los
  ejemplos iniciales, sin concesionario de referencia.
- **Criterios de evaluación**: `config/criterios.yaml`.
- **Conversaciones hechas**: cada práctica queda guardada en `datos/sesiones/` (transcripción
  y devolución). Sirven para revisar cómo actúa el dueño y ajustar las fichas.

## Conversación por voz (ElevenLabs)

Con `ELEVENLABS_API_KEY` cargada, la pantalla de la reunión muestra dos botones:

- **Hablar**: graba al representante; al tocar **Enviar audio**, ElevenLabs lo pasa a texto
  y se envía como un mensaje más. El texto queda visible en el chat.
- **Voz: sí / no**: activa o apaga la voz del dueño. Con la voz activa, cada respuesta se
  escucha además de leerse.

Las voces se eligen en `config/voces.yaml`, una por país y género del dueño (campo
`dueno.genero` de cada ficha: `m` o `f`). La devolución tiene en cuenta que lo hablado es una
transcripción automática y no penaliza errores de reconocimiento.

Sin la clave, el entrenador funciona igual, solo por texto.

### Avatar con cara (Simli)

Con `SIMLI_API_KEY` cargada (además de la de ElevenLabs), la reunión muestra la cara del dueño
hablando. La voz de ElevenLabs se pide en PCM de 16 kHz y va a Simli, que la devuelve con el
video sincronizado. El servidor pide a Simli un permiso por sesión: la clave no llega al
navegador. Las caras se eligen en `config/voces.yaml` (`caras`), una por país y género; por
ahora son caras predefinidas de Simli. Si el avatar no conecta, el dueño sigue hablando solo
con voz. La sesión de Simli se cierra al terminar la práctica, al apagar la voz o tras 3
minutos sin hablar, para no gastar minutos.

Para que la charla sea ágil, el dueño responde con Claude Sonnet 5.5 sin pensar antes
(`MODELO_DIALOGO`), habla frase por frase mientras se genera la respuesta y, con la voz
activa, contesta en hasta tres frases cortas. La devolución sigue con Claude Opus 5.5 (`MODELO`).

## Panel del gestor

En `/gestor` (por ejemplo, http://localhost:8010/gestor) el gestor ve:

- **Por consultor**: cuántos entrenamientos hizo, cuántos con devolución, el último, su
  puntaje promedio y su **progreso** (promedio de las últimas prácticas evaluadas menos el de
  las primeras, hasta tres de cada lado).
- **Mapa de brechas del equipo**: una tabla consultor por criterio con el promedio de sus
  últimas 5 prácticas evaluadas, en rojo lo que está bajo el objetivo y en azul lo que está
  por encima. Arriba dice cuál es la mayor brecha del equipo. El objetivo se fija en
  `config/criterios.yaml` (`objetivo: 7`).
- **Principales puntos de mejora de cada uno**: sus tres criterios más bajos y, a pedido, un
  resumen con IA de lo que más se repite en sus devoluciones (con una frase suya de ejemplo y
  qué practicar). El resumen se guarda y solo se vuelve a pagar si hay prácticas nuevas.
- **Detalle de cada uno**: el puntaje de cada entrenamiento en un gráfico, el cambio por
  criterio y la lista de prácticas, con la conversación completa y la devolución.
- **Códigos de acceso**: crea un código personal por consultor, genera uno nuevo si lo pierde
  o lo desactiva. Con su código, cada práctica queda a su nombre.

Se entra con `CODIGO_GESTOR`. Los consultores y sus códigos se guardan en
`<DATOS_DIR>/consultores.json`, fuera del repositorio. Solo cuenta como entrenamiento una
práctica donde el consultor habló al menos una vez.

## Compartirlo con un tester externo (Railway)

1. Subir esta carpeta a un repositorio **privado** de GitHub. El archivo `.env` y la carpeta
   `datos` quedan afuera solos.
2. En Railway, crear un proyecto desde ese repositorio (**New Project > Deploy from GitHub repo**).
   El archivo `Procfile` indica el comando de inicio.
3. En **Variables**, cargar:
   - `ANTHROPIC_API_KEY`: la clave de Anthropic.
   - `CODIGO_GESTOR`: el código para entrar al panel. Desde ahí se crean los códigos de
     cada consultor.
   - `CODIGO_ACCESO`: opcional, un código compartido para practicar sin identificarse.
     Cuando todos los consultores tengan su código personal, conviene borrarlo para que
     ninguna práctica quede sin nombre.
   - `DATOS_DIR=/data`
   - `ELEVENLABS_API_KEY`: opcional, para la conversación por voz.
   - `SIMLI_API_KEY`: opcional, para el avatar con cara.
4. Agregar un **Volume** montado en `/data`. Ahí quedan las conversaciones de los testers
   entre reinicios.
5. En **Settings > Networking**, elegir **Generate Domain**. Esa dirección y el código de
   acceso son lo que se le pasa al tester.

Para cortar el acceso de un consultor, desactivarlo en el panel; para todos, cambiar los
códigos o borrar el dominio. Conviene además fijar un
límite de gasto mensual en la consola de Anthropic.

## Estructura

- `app/simulador.py`: instrucciones del personaje, llamada a Claude y evaluación.
- `app/servidor.py`: servidor web, sesiones y quién entra con cada código.
- `app/voz.py`: transcripción y voz con ElevenLabs.
- `app/consultores.py`: consultores y sus códigos personales.
- `app/informes.py`: datos del panel del gestor.
- `web/index.html`: pantalla de práctica.
- `web/gestor.html`: panel del gestor.

## Próximas fases

1. Caras propias para el avatar, más parecidas a los dueños de la red.
