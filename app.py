from flask import Flask, request, render_template_string, send_file, redirect
import fitz  # PyMuPDF
import re
import pandas as pd
from io import BytesIO
import threading
import uuid

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

# armazenamento simples (em memória)
resultados = {}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CONTROLE DE PONTO</title>
</head>
<body style="font-family: Arial; text-align:center; background:#f4f4f4">

<div style="background:white; padding:20px; margin:40px auto; width:700px; border-radius:10px;">
    <h2>📄 CONTROLE DE PONTO</h2>

    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="file"><br><br>
        <button type="submit">Analisar</button>
    </form>

    {% if session_id %}
        <p>⏳ Processando arquivo...</p>
        <a href="/resultado/{{session_id}}">Ver resultado</a>
    {% endif %}

</div>
</body>
</html>
"""

RESULTADO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Resultado</title>
</head>
<body style="font-family: Arial; text-align:center; background:#f4f4f4">

<div style="background:white; padding:20px; margin:40px auto; width:700px; border-radius:10px;">

<h2>Resultado</h2>

{% if pronto %}
    <pre>{{ resultado }}</pre>

    <form method="POST" action="/exportar/{{session_id}}">
        <button type="submit">📊 Exportar Excel</button>
    </form>
{% else %}
    <p>⏳ Ainda processando... atualize a página</p>
{% endif %}

</div>
</body>
</html>
"""

# 🔥 NOVO ANALISADOR (super rápido)
def analisar_pdf_bytes(file_bytes):
    dados = {}
    associado_atual = None

    doc = fitz.open(stream=file_bytes, filetype="pdf")

    for page in doc:
        texto = page.get_text()

        if not texto:
            continue

        linhas = texto.split("\n")

        for linha in linhas:
            linha_lower = linha.lower()

            if linha.strip().startswith("Associado"):
                partes = linha.split(":")
                if len(partes) > 1:
                    nome = partes[1].split("Categoria")[0].strip()
                    associado_atual = nome

                    if associado_atual not in dados:
                        dados[associado_atual] = {
                            "faltas": set(),
                            "afastamentos": set()
                        }

            if not associado_atual:
                continue

            data_match = re.search(r"\d{2}/\d{2}/\d{2}", linha)
            if not data_match:
                continue

            data = data_match.group()

            if "afast doenca" in linha_lower:
                dados[associado_atual]["afastamentos"].add(data)

            if "falta injustificada" in linha_lower:
                dados[associado_atual]["faltas"].add(data)

    for nome in dados:
        dados[nome]["faltas"] = list(dados[nome]["faltas"])
        dados[nome]["afastamentos"] = list(dados[nome]["afastamentos"])

    return dados


# 🔄 processamento em background
def processar_background(file_bytes, session_id):
    dados = analisar_pdf_bytes(file_bytes)

    resultado = ""

    for nome, info in dados.items():
        faltas = info["faltas"]
        afast = info["afastamentos"]

        if not faltas and not afast:
            continue

        resultado += f"👤 {nome}\n\n"

        resultado += f"❌ Faltas: {len(faltas)}\n"
        for d in sorted(faltas):
            resultado += f"• {d}\n"

        resultado += f"\n🏥 Afastamentos: {len(afast)}\n"
        for d in sorted(afast):
            resultado += f"• {d}\n"

        resultado += "\n" + "-"*40 + "\n\n"

    resultados[session_id] = {
        "pronto": True,
        "texto": resultado,
        "dados": dados
    }


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        file = request.files["file"]

        if file:
            session_id = str(uuid.uuid4())

            file_bytes = file.read()

            resultados[session_id] = {"pronto": False}

            threading.Thread(
                target=processar_background,
                args=(file_bytes, session_id)
            ).start()

            return render_template_string(HTML, session_id=session_id)

    return render_template_string(HTML)


@app.route("/resultado/<session_id>")
def resultado(session_id):
    info = resultados.get(session_id)

    if not info:
        return "Sessão não encontrada"

    return render_template_string(
        RESULTADO_HTML,
        pronto=info["pronto"],
        resultado=info.get("texto", ""),
        session_id=session_id
    )


@app.route("/exportar/<session_id>", methods=["POST"])
def exportar(session_id):
    info = resultados.get(session_id)

    if not info or not info["pronto"]:
        return "Ainda processando"

    dados = info["dados"]

    output = BytesIO()
    lista = []

    for nome, info in dados.items():
        for d in info["faltas"]:
            lista.append([nome, "Falta Injustificada", d])

        for d in info["afastamentos"]:
            lista.append([nome, "Afastamento", d])

    df = pd.DataFrame(lista, columns=["Associado", "Tipo", "Data"])

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)

    output.seek(0)

    return send_file(output, download_name="relatorio.xlsx", as_attachment=True)


if __name__ == "__main__":
    app.run(debug=False)
