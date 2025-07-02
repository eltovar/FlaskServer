import os
import json
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import requests

# Carga las variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)
port = os.getenv('PORT', '8080')

# Obtiene la URL de la API de Flask API desde las variables de entorno
FLASK_API_URL = os.getenv('FLASK_LANGCHAIN_API_URL')
print(f"Webhook configurado para llamar a la API de FLASK en: {FLASK_API_URL}")

# --- Ruta raíz para servir index.html ---
@app.route('/', methods=['GET'])
def index():
    """Sirve el archivo index.html desde el directorio actual."""
    return send_from_directory(os.getcwd(), 'index.html')

# --- Definición de la Ruta Principal del Webhook ---
@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Maneja las peticiones entrantes del webhook de Dialogflow usando JSON simple.
    """
    req_json = request.json
    
    # Logs para depuración
    print("Petición del Webhook en DialogFlow (body):", json.dumps(req_json, indent=2))
    
    # Extraer información básica del request
    query_result = req_json.get('queryResult', {})
    user_query = query_result.get('queryText', '')
    parameters = query_result.get('parameters', {})
    intent_display_name = query_result.get('intent', {}).get('displayName', '')
    session = req_json.get('session', '')
    
    print(f"Intent activado: {intent_display_name}")
    print(f"Pregunta del Usuario: {user_query}")
    print(f"Parámetros: {parameters}")

    # Respuesta base
    response = {
        "fulfillmentText": "",
        "fulfillmentMessages": [],
        "outputContexts": []
    }

    def set_fulfillment_text(text_content):
        response["fulfillmentText"] = text_content

    def add_quick_replies(text, replies):
        response["fulfillmentMessages"].append({
            "payload": {
                "facebook": {
                    "text": text,
                    "quick_replies": replies
                }
            }
        })

    def set_output_context(context_name, lifespan_count=5):
        response["outputContexts"].append({
            "name": f"{session}/contexts/{context_name}",
            "lifespanCount": lifespan_count
        })

    def clear_output_context(context_name):
        response["outputContexts"].append({
            "name": f"{session}/contexts/{context_name}",
            "lifespanCount": 0
        })

    # --- Manejadores de Intent ---
    def welcome():
        print("Intent 'Default Welcome Intent' activado.")
        set_fulfillment_text('¡Hola! Es un placer saludarte desde el webhook de Flask.')

    def fallback():
        print("Intent 'Default Fallback Intent' activado.")
        set_fulfillment_text('Hola! Soy un bot de Glamping Brillo de Luna. ¿En qué puedo ayudarte?')

    def webhook_prueba():
        print("Intent 'WebhookPrueba' activado.")
        set_fulfillment_text('Hola! Estoy en el webhook de Glamping Brillo de Luna.')

    def main_menu_handler():
        print("Intent 'Primer Menu' activado.")
        set_fulfillment_text("¡Hola! ¿En qué puedo ayudarte hoy?")
        add_quick_replies("¿Qué te gustaría hacer?", [
            {"content_type": "text", "title": "Opciones Glamping", "payload": "GLAMPING_OPTIONS_PAYLOAD"},
            {"content_type": "text", "title": "Más Información", "payload": "MORE_INFO_WEB_PAYLOAD"}
        ])
        set_output_context("main_menu_active")

    def glamping_options_menu_handler():
        print("Intent 'Glamping Options Menu' activado.")
        set_fulfillment_text("¿Sobre qué deseas saber de los glampings?")
        add_quick_replies("Selecciona una opción:", [
            {"content_type": "text", "title": "Preguntar al Agente IA", "payload": "ASK_AI_AGENT_PAYLOAD"},
            {"content_type": "text", "title": "Reservas", "payload": "RESERVATIONS_PAYLOAD"},
            {"content_type": "text", "title": "Tarifas", "payload": "RATES_PAYLOAD"},
            {"content_type": "text", "title": "Ubicación", "payload": "LOCATION_PAYLOAD"}
        ])
        set_output_context("glamping_options_menu_active")
        clear_output_context("main_menu_active")

    def ask_ai_agent_handler():
        print("Intent 'Ask AI Agent' activado.")
        set_fulfillment_text("Claro, por favor, dime tu pregunta para el agente de IA.")
        clear_output_context("glamping_options_menu_active")
        set_output_context("awaiting_ai_query")

    def langchain_agent():
        print(f"Intent para Agente LangChain activado. Pregunta: \"{user_query}\"")
        
        if not FLASK_API_URL:
            print("ERROR: FLASK_LANGCHAIN_API_URL no está configurada")
            set_fulfillment_text("Lo siento, el servicio no está disponible temporalmente.")
            return

        try:
            api_response = requests.post(
                FLASK_API_URL,
                json={"query": user_query, "parameters": parameters},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            api_response.raise_for_status()
            
            result = api_response.json()
            if result and result.get('answer'):
                set_fulfillment_text(result['answer'])
                print("Respuesta del agente IA:", result['answer'])
            else:
                set_fulfillment_text("No pude obtener una respuesta del agente. ¿Podrías intentar de otra forma?")
                
        except requests.exceptions.RequestException as e:
            print(f"Error al llamar a la API: {e}")
            set_fulfillment_text("Lo siento, no pude contactar el servicio de información. Intenta más tarde.")

    # --- Mapeo de Intents ---
    intent_map = {
        'Default Welcome Intent': welcome,
        'Default Fallback Intent': fallback,
        'WebhookPrueba': webhook_prueba,
        'Primer Menu': main_menu_handler,
        'Glamping Options Menu': glamping_options_menu_handler,
        'Ask AI Agent': ask_ai_agent_handler,
        'langchainAgent': langchain_agent
    }

    # Ejecutar el manejador correspondiente
    handler = intent_map.get(intent_display_name)
    if handler:
        handler()
    else:
        print(f"No se encontró manejador para: {intent_display_name}")
        set_fulfillment_text("Lo siento, no entiendo lo que quieres decir.")

    return jsonify(response)

# --- Inicia el servidor de Flask ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(port), debug=True)

print(f"URL del Agente IA Externo: {FLASK_API_URL}")
print(f"Servidor Flask corriendo en http://localhost:{port}")