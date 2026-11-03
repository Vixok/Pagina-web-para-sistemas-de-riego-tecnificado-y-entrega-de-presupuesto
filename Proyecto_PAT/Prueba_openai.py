from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()

cliente = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ==========================================
# PRUEBA MODELO OPERATIVO
# ==========================================
resp_mini = cliente.responses.create(
    model="gpt-4o-mini",
    instructions="Responde con una única palabra.",
    input="Escribe: OK",
)

print("GPT-4o-mini")
print("Estado:", resp_mini.status)
print("Respuesta:", resp_mini.output_text)

# ==========================================
# PRUEBA MODELO JUDGE
# ==========================================
resp_judge = cliente.responses.create(
    model="gpt-4o",
    instructions=(
        "Eres un verificador técnico. "
        "Para esta prueba responde únicamente con la palabra OK."
    ),
    input="Verifica que esta llamada funciona.",
)

print("\nGPT-4o")
print("Estado:", resp_judge.status)
print("Respuesta:", resp_judge.output_text)