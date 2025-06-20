import os
import json
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import requests
import asyncio # Necesario para ejecutar funciones asíncronas

# Importa los módulos necesarios de google-cloud-dialogflow
from google.cloud.dialogflow_v2.types import WebhookRequest, WebhookResponse
from google.protobuf.json_format import ParseDict, MessageToJson

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
    try:
        dialogflow_request = ParseDict(req_json, WebhookRequest())
    except Exception as e:
        print(f"Error al parsear la petición del webhook de Dialogflow: {e}")
        return jsonify({"fulfillmentText": "Error interno al procesar la solicitud."}), 400

    # Inicializa un objeto WebhookResponse para construir nuestra respuesta
    dialogflow_response = WebhookResponse()

    # Extrae información relevante de la petición parseada
    query_result = dialogflow_request.query_result
    user_query = query_result.query_text
    parameters = query_result.parameters
    intent_display_name = query_result.intent.display_name

    print(f"Intent activado: {intent_display_name}")
    print(f"Pregunta del Usuario: {user_query}")
    print(f"Parámetros: {dict(parameters)}") # Convierte el mapa protobuf a diccionario para imprimir

    # --- Funciones de Manejo de Intents (ahora manipulando directamente dialogflow_response) ---
    def set_fulfillment_text(response_obj, text):
        """Función auxiliar para establecer fulfillmentText."""
        response_obj.fulfillment_text = text

    def add_fulfillment_message(response_obj, text):
        """Función auxiliar para añadir un mensaje de texto a fulfillmentMessages."""
        from google.cloud.dialogflow_v2.types import Text
        response_obj.fulfillment_messages.append(Text(text=[text]))

    def welcome():
        """Maneja el 'Default Welcome Intent'."""
        print("Intent 'Default Welcome Intent' activado.")
        set_fulfillment_text(dialogflow_response, '¡Hola! Es un placer saludarte desde el webhook de Flask con la librería oficial.')

    def fallback():
        """Maneja el 'Default Fallback Intent'."""
        print("Intent 'Default Fallback Intent' activado.")
        set_fulfillment_text(dialogflow_response, 'Hola!!, soy un bot de prueba pero no tengo nada que decirte.')

    def webhook_prueba():
        """Maneja el 'WebhookPrueba' Intent."""
        print("Intent 'WebhookPrueba' activado.")
        set_fulfillment_text(dialogflow_response, 'Hola!!, estoy en el webhook de prueba de Flask con la librería oficial.')

    def decir_hola():
        """Maneja el Intent 'decirHola' (con extracción del parámetro 'person')."""
        print("Parámetros recibidos:", dict(parameters))
        # Los parámetros ahora se acceden directamente desde el objeto `parameters` (Map de protobuf)
        person_object = parameters.get('person')

        person_name = None
        if person_object:
            # Dialogflow puede enviar estructuras complejas para entidades; para @sys.person
            # podría ser una estructura con 'name' o simplemente una cadena.
            if hasattr(person_object, 'string_value') and person_object.string_value:
                person_name = person_object.string_value
            elif hasattr(person_object, 'struct_value') and person_object.struct_value.fields.get('name'):
                 person_name = person_object.struct_value.fields['name'].string_value
            elif isinstance(person_object, str) and person_object: # Fallback si es una cadena simple directamente
                 person_name = person_object
            else:
                 # Intenta convertir a cadena si es un tipo de valor protobuf como Value
                 try:
                     person_name = str(person_object)
                 except Exception:
                     pass # No se pudo convertir a cadena
        
        if person_name and person_name not in ["null", "undefined", "[object Object]"]: # Filtro básico
            set_fulfillment_text(dialogflow_response, f'¡Hola, {person_name}! Es un placer saludarte desde el webhook de Flask.')
        else:
            set_fulfillment_text(dialogflow_response, '¡Hola! Es un placer saludarte desde el webhook de Flask.')

    # --- Función ASÍNCRONA para Llamar a la API del Agente Python (Flask) ---
    async def langchain_agent():
        """Llama a un agente Flask externo y popula dialogflow_response."""
        print(f"Intent para Agente LangChain activado. Pregunta del usuario: \"{user_query}\"")
        # Convierte los parámetros protobuf a un diccionario Python estándar para la API externa
        dialogflow_parameters_dict = dict(parameters)
        print("Parámetros de Dialogflow (para API externa):", json.dumps(dialogflow_parameters_dict, indent=2))

        if not FLASK_API_URL:
            print("ERROR: FLASK_LANGCHAIN_API_URL no está configurada en .env")
            set_fulfillment_text(dialogflow_response, "Lo siento, aún no tenemos información disponible.")
            return

        try:
            response = requests.post(
                FLASK_API_URL,
                json={
                    "query": user_query,
                    "parameters": dialogflow_parameters_dict # Envía como diccionario regular
                },
                headers={
                    'Content-Type': 'application/json'
                }
            )
            response.raise_for_status() # Lanza un HTTPError para respuestas malas (4xx o 5xx)

            api_response = response.json()

            if api_response and isinstance(api_response.get('answer'), str) and len(api_response.get('answer')) > 0:
                set_fulfillment_text(dialogflow_response, api_response['answer'])
                print("Respuesta de la API de Flask enviada a Dialogflow:", api_response['answer'])
            else:
                set_fulfillment_text(dialogflow_response, "No pude obtener una respuesta clara del sistema de información. ¿Podrías intentar de otra forma?")
                print(f"La API de Flask no devolvió la clave 'answer' esperada o está vacía: {api_response}")

        except requests.exceptions.RequestException as e:
            print(f"Error al llamar a la API de Flask: {e}")
            if e.response:
                print(f"Respuesta de error de Flask: {e.response.text}")
                if e.response.status_code == 404:
                    set_fulfillment_text(dialogflow_response, "Lo siento, no pude conectar con el servicio de información (error 404). Asegúrate de que la URL sea correcta y el servicio esté en línea.")
                elif e.response.status_code == 500:
                    set_fulfillment_text(dialogflow_response, "Hubo un error interno en el servicio de información. Por favor, intenta de nuevo o contacta al soporte.")
                else:
                    set_fulfillment_text(dialogflow_response, f"Hubo un problema ({e.response.status_code}) al procesar tu solicitud con el sistema de información. Intenta de nuevo.")
            else:
                set_fulfillment_text(dialogflow_response, "Lo siento, no pude contactar el sistema de información. Verifica tu conexión o intenta más tarde.")


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
        if hasattr(handler, '__annotations__') and 'async' in handler.__annotations__.values():
            asyncio.run(handler())
        else:
            handler()
    else:
        print(f"No se encontró un manejador para el intent: {intent_display_name}")
        set_fulfillment_text(dialogflow_response, "Lo siento, no entiendo lo que quieres decir.")

    # Convierte el objeto WebhookResponse de nuevo a JSON para Dialogflow
    return jsonify(json.loads(MessageToJson(dialogflow_response)))

# --- Inicia el servidor de Flask ---
if __name__ == '__main__':
    # Cuando se ejecuta localmente, asegúrate de que 'index.html' esté en el mismo directorio.
    app.run(host='0.0.0.0', port=port, debug=True) # debug=True para desarrollo, False en producción
    print(f"Servidor corriendo en http://localhost:{port}")
    print(f"URL del Agente Python Flask: {FLASK_API_URL}")
