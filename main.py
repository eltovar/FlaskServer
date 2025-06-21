import os
import json
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import requests
  # Necesario para ejecutar funciones asíncronas

# Importa los módulos necesarios de google-cloud-dialogflow
from google.cloud.dialogflow_v2.types import WebhookRequest, WebhookResponse
from google.protobuf.json_format import MessageToJson

# Carga las variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)
port = os.getenv('PORT', 8080) # Usa PORT desde .env o por defecto 8080

# Obtiene la URL de la API de Flask API desde las variables de entorno
FLASK_API_URL = os.getenv('FLASK_LANGCHAIN_API_URL')
print(f"Webhook configurado para llamar a la API de FLASK en: {FLASK_API_URL}")

# --- Ruta raíz para servir index.html ---
@app.route('/', methods=['GET'])
def index():
    """Sirve el archivo index.html desde el directorio actual."""
    return send_from_directory(os.getcwd(), 'index.html')

# --- Definición de la Ruta Principal del Webhook ---
# Esta es la ruta a la que Dialogflow enviará las peticiones HTTP POST.
@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Maneja las peticiones entrantes del webhook de Dialogflow usando la librería google-cloud-dialogflow.
    """
    # `request.json` parsea automáticamente el payload JSON entrante
    req_json = request.json

    # Logs para depuración
    print("Petición del Webhook en DialogFlow (headers):", json.dumps(dict(request.headers), indent=2))
    print("Petición del Webhook en DialogFlow (body):", json.dumps(req_json, indent=2))

    # Parsea la petición JSON entrante en un objeto WebhookRequest
    # Esto aprovecha los tipos oficiales de Dialogflow para un acceso estructurado
    query_result = req_json.get('queryResult', {})
    user_query = query_result.get('queryText', '')
    parameters = query_result.get('parameters', {})
    intent_display_name = query_result.get('intent', {}).get('displayName', '')

    print(f"Intent activado: {intent_display_name}")
    print(f"Pregunta del Usuario: {user_query}")
    print(f"Parámetros recibidos (raw): {json.dumps(parameters, indent=2)}")

    # Objeto de respuesta que enviaremos de vuelta a Dialogflow
    # Por defecto, Dialogflow espera un JSON con 'fulfillmentText' o 'fulfillmentMessages'.
    # Construimos un diccionario simple y luego lo convertimos a JSON con jsonify.
    response_data = {
        "fulfillmentText": "",
        "fulfillmentMessages": []
    }

    # --- Funciones de Manejo de Intents ---
    # Estas funciones ahora modificarán directamente el diccionario `response_data`.

    def set_fulfillment_text(text):
        response_data["fulfillmentText"] = text

    def add_fulfillment_message(text):
        # Dialogflow puede aceptar múltiples mensajes de texto en fulfillmentMessages
        response_data["fulfillmentMessages"].append({"text": {"text": [text]}})

    def welcome():
        print("Intent 'Default Welcome Intent' activado.")
        set_fulfillment_text('¡Hola! Es un placer saludarte desde el webhook de Flask con el nuevo parser.')

    def fallback():
        print("Intent 'Default Fallback Intent' activado.")
        set_fulfillment_text('Hola!!, soy un bot de prueba pero no tengo nada que decirte.')

    def webhook_prueba():
        print("Intent 'WebhookPrueba' activado.")
        set_fulfillment_text('Hola!!, estoy en el webhook de prueba de Flask con el nuevo parser.')

    def decir_hola():
        print("Maneja el Intent 'decirHola'. Parámetros recibidos:", json.dumps(parameters))
        
        person_object = parameters.get('person')
        person_name = None

        # La entidad @sys.person a menudo viene como un objeto con una clave 'name'
        if isinstance(person_object, dict) and 'name' in person_object:
            person_name = person_object['name']
        elif isinstance(person_object, str) and person_object:
            person_name = person_object
        
        if person_name and person_name.strip() and person_name not in ["null", "undefined", "[object Object]"]:
            set_fulfillment_text(f'¡Hola, {person_name}! Es un placer saludarte desde el webhook de Flask.')
        else:
            set_fulfillment_text('¡Hola! Es un placer saludarte desde el webhook de Flask.')

    # --- Función ASÍNCRONA para Llamar a la API del Agente IA (FLASK) ---
    async def langchain_agent():
        print(f"Intent para Agente LangChain activado. Pregunta del usuario: \"{user_query}\"")
        print("Parámetros de Dialogflow (para API externa):", json.dumps(parameters, indent=2))

        if not FLASK_API_URL:
            print("ERROR: FLASK_LANGCHAIN_API_URL no está configurada en .env")
            set_fulfillment_text("Lo siento, aún no tenemos información disponible. (Error de configuración)")
            return

        try:
            response = requests.post(
                FLASK_API_URL,
                json={
                    "query": user_query,
                    "parameters": parameters # Envía el diccionario de parámetros directamente
                },
                headers={
                    'Content-Type': 'application/json'
                }
            )
            response.raise_for_status() # Lanza un HTTPError para respuestas malas (4xx o 5xx)

            api_response = response.json()
            
            if api_response and isinstance(api_response.get('answer'), str) and len(api_response.get('answer')) > 0:
                set_fulfillment_text(api_response['answer'])
                print("Respuesta de la API externa enviada a Dialogflow:", api_response['answer'])
            else:
                set_fulfillment_text("No pude obtener una respuesta clara del sistema de información. ¿Podrías intentar de otra forma?")
                print(f"La API externa no devolvió la clave 'answer' esperada o está vacía: {api_response}")

        except requests.exceptions.RequestException as e:
            print(f"Error al llamar a la API externa: {e}")
            if e.response:
                print(f"Respuesta de error de la API externa: {e.response.text}")
                if e.response.status_code == 404:
                    set_fulfillment_text("Lo siento, no pude conectar con el servicio de información (error 404). Asegúrate de que la URL sea correcta y el servicio esté en línea.")
                elif e.response.status_code == 500:
                    set_fulfillment_text("Hubo un error interno en el servicio de información. Por favor, intenta de nuevo o contacta al soporte.")
                else:
                    set_fulfillment_text(f"Hubo un problema ({e.response.status_code}) al procesar tu solicitud con el sistema de información. Intenta de nuevo.")
            else:
                set_fulfillment_text("Lo siento, no pude contactar el sistema de información. Verifica tu conexión o intenta más tarde.")


    # --- Mapeo de Intents a funciones manejadoras ---
    intent_map = {
        'Default Welcome Intent': welcome,
        'Default Fallback Intent': fallback,
        'WebhookPrueba': webhook_prueba,
        'decirHola': decir_hola,
        'langchainAgent': langchain_agent,
    }

    # Obtiene la función manejadora basada en el nombre de display del intent
    handler = intent_map.get(intent_display_name)

    if handler:
        # Si el manejador es una función asíncrona, ejecútala usando asyncio
        # Esto es importante para funciones que hacen llamadas a APIs externas (requests.post es síncrono, pero se usa en una función async)
        # requests es síncrono, por lo que el uso de asyncio.run() aquí no hará que la llamada a requests sea asíncrona.
        # Para verdaderas operaciones asíncronas, se usaría aiohttp o httpx con async/await.
        # Sin embargo, mantener la estructura async para 'langchain_agent' está bien si en el futuro planeas usar librerías async.
        # Por ahora, asyncio.run() simplemente bloquea el hilo hasta que la función síncrona (requests.post) termina.
        if asyncio.iscoroutinefunction(handler): # Mejor verificación para funciones coroutine
            asyncio.run(handler())
        else:
            handler()
    else:
        print(f"No se encontró un manejador para el intent: {intent_display_name}")
        set_fulfillment_text("Lo siento, no entiendo lo que quieres decir.")

    # Retorna la respuesta en formato JSON que Dialogflow espera
    return jsonify(response_data)

# --- Inicia el servidor de Flask ---
if __name__ == '__main__':
    # Cuando se ejecuta localmente, asegura que 'index.html' esté en el mismo directorio.
    # En producción (Railway), Railway se encarga de la ejecución y el manejo de puertos.
    # La variable PORT es inyectada por Railway.
    app.run(host='0.0.0.0', port=int(port), debug=True) # debug=True para desarrollo, False en producción
    print(f"Servidor Flask corriendo en http://localhost:{port}")
    print(f"URL del Agente IA Externo: {FLASK_API_URL}")
