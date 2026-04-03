from flask import Flask, request, render_template_string, send_file
import pdfplumber
import re
import pandas as pd
from io import BytesIO
import json
import webbrowser
import threading

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CONTROLE DE PONTO</title>
    <style>
        body { font-family: Arial; background: #f4f4f4; text-align: center; }
        .box { background: white; padding: 20px; margin: 40px auto; width: 700px; border-radius: 10px; box-shadow: 0px 0px 10px #ccc; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #0056b3; }
        pre { text-align: left; background: #eee; padding: 10px; border-radius: 5px; }
        .filtros { margin: 10px; }
    </style>
</head>
<body>

<div class="box">
    <h2>📄 CONTROLE DE PONTO</h2>

    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="file"><br><br>

        <div class="filtros">
            <label><input type="checkbox" name="mostrar_faltas" checked> Mostrar Faltas</label><br>
            <label><input type="checkbox" name="mostrar_afastamentos" checked> Mostrar Afastamentos</label>
        </div>

        <button type="submit">Analisar</button>
    </form>

    {% if resultado %}
        <h3>Resultado</h3>
        <pre>{{ resultado }}</pre>

        <form method="POST" action="/exportar">
            <input type="hidden" name="dados" value='{{ dados | tojson }}'>
            <button type="submit">📊 Exportar Excel</button>
        </form>
    {% endif %}
</div>

</body>
</html>
"""

def analisar_pdf(file):
    dados = {}
    associado_atual = None

    with pdfplumber.open(file) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            linhas = texto.split("\n")

            for linha in linhas:
                linha_lower = linha.lower()

                if linha.strip().startswith("Associado"):
                    partes = linha.split(":")
                    if len(partes) > 1:
                        nome_limpo = partes[1].split("Categoria")[0].strip()
                        associado_atual = nome_limpo
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

                if "falta" in linha_lower and "falta injustificada" in linha_lower:
                    dados[associado_atual]["faltas"].add(data)

    for nome in dados:
        dados[nome]["faltas"] = list(dados[nome]["faltas"])
        dados[nome]["afastamentos"] = list(dados[nome]["afastamentos"])

    return dados


@app.route("/", methods=["GET", "POST"])
def home():
    resultado = None
    dados = {}

    if request.method == "POST":
        file = request.files["file"]

        mostrar_faltas = request.form.get("mostrar_faltas")
        mostrar_afastamentos = request.form.get("mostrar_afastamentos")

        if file:
            dados = analisar_pdf(file)

            resultado = ""

            for nome, info in dados.items():

                faltas = info["faltas"] if mostrar_faltas else []
                afast = info["afastamentos"] if mostrar_afastamentos else []

                if not faltas and not afast:
                    continue

                resultado += f"👤 {nome}\n\n"

                if mostrar_faltas:
                    resultado += f"❌ Faltas: {len(faltas)}\n"
                    for d in sorted(faltas):
                        resultado += f"• {d}\n"

                if mostrar_afastamentos:
                    resultado += f"\n🏥 Afastamentos: {len(afast)}\n"
                    for d in sorted(afast):
                        resultado += f"• {d}\n"

                resultado += "\n" + "-"*40 + "\n\n"

    return render_template_string(HTML, resultado=resultado, dados=dados)


@app.route("/exportar", methods=["POST"])
def exportar():
    dados = json.loads(request.form["dados"])

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


def abrir_navegador():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    threading.Timer(1, abrir_navegador).start()
    app.run(debug=False)
