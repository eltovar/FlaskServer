import os
import json
import asyncio # Necesario para ejecutar funciones asíncronas
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import requests 


# Importa los módulos necesarios de Flask y dotenv
from google.cloud.dialogflow_v2.types import WebhookRequest, WebhookResponse, Message, Text
from google.protobuf.json_format import ParseDict, MessageToJson
from google.protobuf.struct_pb2 import Struct  # Necesario para custom payloads como los de Facebook

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
    
    try:
        dialogflow_request = ParseDict(req_json, WebhookRequest())
    except Exception as e:
        print(f"Error al parsear la petición del webhook de Dialogflow: {e}")
        return jsonify({"fulfillmentText": "Error interno al procesar la solicitud."}), 400


    # Parsea la petición JSON entrante en un objeto WebhookRequest
    dialogflow_response = WebhookResponse()
    #dialogflow_request =  WebhookRequest()
    
    # Esto aprovecha los tipos oficiales de Dialogflow para un acceso estructurado
    query_result = dialogflow_request.query_result
    user_query = query_result.query_text
    parameters = query_result.parameters
    intent_display_name = query_result.intent.display_name
    
    #user_query = query_result.get('queryText', '')
    #parameters = query_result.get('parameters', {})
    #intent_display_name = query_result.get('intent', {}).get('displayName', '')


    print(f"Intent activado: {intent_display_name}")
    print(f"Pregunta del Usuario: {user_query}")
    print(f"Parámetros: {dict(parameters)}")

    # Objeto de respuesta que enviaremos de vuelta a Dialogflow
    # Por defecto, Dialogflow espera un JSON con 'fulfillmentText' o 'fulfillmentMessages'.
    # Construimos un diccionario simple y luego lo convertimos a JSON con jsonify.
    
    #response_data = {
     #   "fulfillmentText": "",
     #   "fulfillmentMessages": []
    #}

    # --- Funciones de Manejo de Intents ---
    # Estas funciones ahora modificarán directamente el diccionario `response_data`.

#Funciones auxiliares para manejar la respuesta de Dialogflow
    def set_fulfillment_text(response_obj, text):
        response_obj.fulfillment_text = text

    def add_fulfillment_message(response_obj, text_content):
        # Dialogflow puede aceptar múltiples mensajes de texto en fulfillmentMessages
        response_obj.fulfillment_messages.append(Message(text=Text(text=[text_content])))
       
    def add_custom_payload(response_obj, payload_dict):
        """
        Añade un payload personalizado a la respuesta de Dialogflow.
        Esto es ideal para rich responses específicos de plataforma como los de Facebook Messenger,
        que a menudo son interpretados por los proveedores de WhatsApp.
        """
        try:
            payload_struct = ParseDict(payload_dict, Struct())
            response_obj.fulfillment_messages.append(Message(payload=payload_struct))
        except Exception as e:
            print(f"Error al crear el custom payload: {e}")
            add_fulfillment_message(response_obj, "Lo siento, hubo un problema al generar las opciones de menú.")

    def set_output_context(response_obj, session_path, context_name, lifespan_count=5):
        """Helper para establecer contextos de salida."""
        response_obj.output_contexts.append(        
            f"{session_path}/contexts/{context_name}"
        )
        # Nota: La librería de Dialogflow v2 (protobufs) no tiene lifespan_count directo en set_output_context.
        # Si necesitas controlar el lifespan, deberías construir el `Context` object completo.
        # Para limpiar contextos, se usa "?lifespan_count=0" en el nombre del contexto, como se muestra abajo.

    def clear_output_context(response_obj, session_path, context_name):
        """Helper para limpiar contextos de salida."""
        response_obj.output_contexts.append(
            f"{session_path}/contexts/{context_name}?lifespan_count=0"
        )

    def welcome():
        print("Intent 'Default Welcome Intent' activado.")
        set_fulfillment_text(dialogflow_response, '¡Hola! Es un placer saludarte desde el webhook de Flask con el nuevo parser.')

    def fallback():
        print("Intent 'Default Fallback Intent' activado.")
        set_fulfillment_text(dialogflow_response,'Hola!!, soy un bot de prueba pero no tengo nada que decirte.')

    def webhook_prueba():
        print("Intent 'WebhookPrueba' activado.")
        set_fulfillment_text(dialogflow_response,'Hola!!, estoy en el webhook de prueba de Flask con el nuevo parser.')

    def decir_hola():
        """Maneja el Intent 'decirHola' (con extracción del parámetro 'person')."""
        print("Parámetros recibidos:", dict(parameters))
        person_object = parameters.get('person')

        person_name = None
        if person_object:
            if hasattr(person_object, 'string_value') and person_object.string_value:
                person_name = person_object.string_value
            elif hasattr(person_object, 'struct_value') and person_object.struct_value.fields.get('name'):
                 person_name = person_object.struct_value.fields['name'].string_value
            elif isinstance(person_object, str) and person_object:
                 person_name = person_object
            else:
                 try:
                     person_name = str(person_object)
                 except Exception:
                     pass
        
        if person_name and person_name not in ["null", "undefined", "[object Object]"]:
            set_fulfillment_text(dialogflow_response, f'¡Hola, {person_name}! Es un placer saludarte desde el webhook de Flask.')
        else:
            set_fulfillment_text(dialogflow_response, '¡Hola! Es un placer saludarte desde el webhook de Flask.')

    def main_menu_handler():
        """Maneja el Intent 'Main Menu' para mostrar el menú principal."""
        print("Intent 'Main Menu' activado.")
        set_fulfillment_text(dialogflow_response, "¡Hola! ¿En qué puedo ayudarte hoy?")
        add_custom_payload(dialogflow_response, {
            "facebook": {
                "text": "¿Qué te gustaría hacer?",
                "quick_replies": [
                    {"content_type": "text", "title": "Opciones Glamping", "payload": "GLAMPING_OPTIONS_PAYLOAD"},
                    {"content_type": "text", "title": "Más Información", "payload": "MORE_INFO_WEB_PAYLOAD"}
                ]
            }
        })
        # Establece el contexto de salida para el siguiente paso del menú
        set_output_context(dialogflow_response, dialogflow_request.session, "main_menu_active")

    def glamping_options_menu_handler():
        """Maneja el Intent 'Glamping Options Menu' para mostrar el submenú de glamping."""
        print("Intent 'Glamping Options Menu' activado.")
        set_fulfillment_text(dialogflow_response, "¿Sobre qué deseas saber de los glampings?")
        add_custom_payload(dialogflow_response, {
            "facebook": {
                "text": "Selecciona una opción:",
                "quick_replies": [
                    {"content_type": "text", "title": "Preguntar al Agente IA", "payload": "ASK_AI_AGENT_PAYLOAD"},
                    {"content_type": "text", "title": "Reservas", "payload": "RESERVATIONS_PAYLOAD"},
                    {"content_type": "text", "title": "Tarifas", "payload": "RATES_PAYLOAD"},
                    {"content_type": "text", "title": "Ubicación", "payload": "LOCATION_PAYLOAD"},
                ]
            }
        })
        # Establece el contexto de salida
        set_output_context(dialogflow_response, dialogflow_request.session, "glamping_options_menu_active")
        # Elimina el contexto anterior para limpiar el estado
        clear_output_context(dialogflow_response, dialogflow_request.session, "main_menu_active")

    def ask_ai_agent_handler():
        """Maneja el Intent para solicitar una pregunta al agente IA."""
        print("Intent 'Ask AI Agent Trigger' activado.")
        set_fulfillment_text(dialogflow_response, "Claro, por favor, dime tu pregunta para el agente de IA.")
        # Limpia el contexto del menú de opciones de glamping
        clear_output_context(dialogflow_response, dialogflow_request.session, "glamping_options_menu_active")
        # Establece un contexto para esperar la pregunta del usuario
        set_output_context(dialogflow_response, dialogflow_request.session, "awaiting_ai_query")

    def email_notification_handler():
        """Maneja las opciones que requieren notificación por email."""
        print("Intent 'EmailNotification_Intent' activado.")
        # El user_query contendrá el texto del botón clickeado o el payload si se configura así en Dialogflow
        selected_option_text = user_query 

        topic_map = {
            "Reservas": "reservas",
            "Tarifas": "tarifas",
            "Ubicación": "ubicación",
            "RESERVATIONS_PAYLOAD": "reservas", # Si el payload llega como query_text
            "RATES_PAYLOAD": "tarifas",
            "LOCATION_PAYLOAD": "ubicación"
        }
        topic = topic_map.get(selected_option_text, "información general")

        set_fulfillment_text(dialogflow_response, f"Recibido. Te enviaremos información sobre {topic} a tu correo electrónico registrado. ¡Gracias!")
        # Placeholder para la lógica de notificación por email
        print(f"DEBUG: Se debería enviar un correo electrónico sobre {topic}.")
        # Limpia el contexto del menú de opciones de glamping
        clear_output_context(dialogflow_response, dialogflow_request.session, "glamping_options_menu_active")

    def send_to_web_handler():
        """Maneja la opción de redirigir al usuario a una página web."""
        print("Intent 'SendToWeb_Intent' activado.")
        set_fulfillment_text(dialogflow_response, "Puedes encontrar más información detallada en nuestra página web:")
        add_fulfillment_message(dialogflow_response, "Visita: https://www.ejemplo-glamping.com")
        # Limpia el contexto del menú principal
        clear_output_context(dialogflow_response, dialogflow_request.session, "main_menu_active")

            
        

    # -- Función ASÍNCRONA para Llamar a la API del Agente IA (FLASK) ---
    async def langchain_agent():
        print(f"Intent para Agente LangChain activado. Pregunta del usuario: \"{user_query}\"")
        dialogflow_parameters_dic = dict(parameters)  # Convierte los parámetros a un diccionario normal
        print("Parámetros de Dialogflow (para API externa):", json.dumps(dialogflow_parameters_dic, indent=2))

        if not FLASK_API_URL:
            print("ERROR: FLASK_LANGCHAIN_API_URL no está configurada en .env")
            set_fulfillment_text(dialogflow_response,"Lo siento, aún no tenemos información disponible. (Error de configuración)")
            return

        try:
            response = requests.post(
                FLASK_API_URL,
                json={
                    "query": user_query,
                    "parameters": dialogflow_parameters_dic # Envía el diccionario de parámetros directamente
                },
                headers={
                    'Content-Type': 'application/json'
                }
            )
            response.raise_for_status() # Lanza un HTTPError para respuestas malas (4xx o 5xx)

            api_response = response.json()
            
            if api_response and isinstance(api_response.get('answer'), str) and len(api_response.get('answer')) > 0:
                set_fulfillment_text(dialogflow_response, api_response['answer'])
                print("Respuesta de la API externa enviada a Dialogflow:", api_response['answer'])
            else:
                set_fulfillment_text(dialogflow_response,"No pude obtener una respuesta clara del sistema de información. ¿Podrías intentar de otra forma?")
                print(f"La API externa no devolvió la clave 'answer' esperada o está vacía: {api_response}")

        except requests.exceptions.RequestException as e:
            print(f"Error al llamar a la API de FastAPI: {e}")
            if e.response:
                print(f"Respuesta de error de Flask/FastAPI: {e.response.text}")
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
        'Main Menu': main_menu_handler,
        'Glamping Options Menu': glamping_options_menu_handler,
        'Ask AI Agent Trigger': ask_ai_agent_handler,
        'EmailNotification_Intent': email_notification_handler,
        'SendToWeb_Intent': send_to_web_handler,
        'langchainAgent': langchain_agent
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
        set_fulfillment_text(dialogflow_response, "Lo siento, no entiendo lo que quieres decir.")

    # Retorna la respuesta en formato JSON que Dialogflow espera
    return jsonify(json.loads(MessageToJson(dialogflow_response)))

# --- Inicia el servidor de Flask ---
if __name__ == '__main__':
    # Cuando se ejecuta localmente, asegura que 'index.html' esté en el mismo directorio.
    # En producción (Railway), Railway se encarga de la ejecución y el manejo de puertos.
    # La variable PORT es inyectada por Railway.
    app.run(host='0.0.0.0', port=(port), debug=True) # debug=True para desarrollo, False en producción
    print(f"Servidor Flask corriendo en http://localhost:{port}")
    print(f"URL del Agente IA Externo: {FLASK_API_URL}")
