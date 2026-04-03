from flask import Flask, request, jsonify, render_template_string
import pdfplumber
import re
import uuid
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Controle de Ponto</title>
</head>
<body style="font-family: Arial; text-align:center;">

<h2>📊 Controle de Ponto</h2>

<form method="POST" action="/upload" enctype="multipart/form-data">
    <input type="file" name="file" required><br><br>
    <button type="submit">Analisar</button>
</form>

<pre style="text-align:left; margin:20px;">
{{ resultado }}
</pre>

</body>
</html>
"""

def analisar_pdf(filepath):
    dados = {}
    associado_atual = None

    with pdfplumber.open(filepath) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            for linha in texto.split("\\n"):
                linha_lower = linha.lower()

                # IDENTIFICA ASSOCIADO
                if "associado" in linha_lower:
                    partes = linha.split(":")
                    if len(partes) > 1:
                        nome = partes[1].split("Categoria")[0].strip()
                        associado_atual = nome

                        if nome not in dados:
                            dados[nome] = {"faltas": [], "afastamentos": []}

                if not associado_atual:
                    continue

                # PEGA DATA
                data_match = re.search(r"\\d{2}/\\d{2}/\\d{2}", linha)
                if not data_match:
                    continue

                data = data_match.group()

                # 🔥 VOLTA PARA PADRÃO ORIGINAL (FUNCIONAVA)
                if "falta injustificada" in linha_lower:
                    if data not in dados[associado_atual]["faltas"]:
                        dados[associado_atual]["faltas"].append(data)

                if "afast doenca" in linha_lower:
                    if data not in dados[associado_atual]["afastamentos"]:
                        dados[associado_atual]["afastamentos"].append(data)

    resultado = ""

    for nome, info in dados.items():
        if not info["faltas"] and not info["afastamentos"]:
            continue

        resultado += f"👤 {nome}\\n\\n"

        resultado += f"❌ Faltas injustificadas: {len(info['faltas'])}\\n"
        for f in info["faltas"]:
            resultado += f"- {f}\\n"

        resultado += f"\\n🏥 Afastamentos: {len(info['afastamentos'])}\\n"
        for a in info["afastamentos"]:
            resultado += f"- {a}\\n"

        resultado += "\\n------------------------\\n\\n"

    return resultado


@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML, resultado="")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]

    filepath = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
    file.save(filepath)

    resultado = analisar_pdf(filepath)

    return render_template_string(HTML, resultado=resultado)


if __name__ == "__main__":
    app.run(debug=True)
