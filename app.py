from flask import Flask, request, render_template_string, send_file
import pdfplumber
import re
import pandas as pd
from io import BytesIO
import json
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Controle de Ponto</title>
    <style>
        body { font-family: Arial; background: #f4f4f4; text-align: center; }
        .box { background: white; padding: 20px; margin: 40px auto; width: 750px; border-radius: 10px; box-shadow: 0px 0px 10px #ccc; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #0056b3; }
        pre { text-align: left; background: #eee; padding: 10px; border-radius: 5px; }
        .filtros { margin: 10px; }
    </style>
</head>
<body>

<div class="box">
    <h2>📊 Controle de Ponto</h2>

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
            try:
                texto = pagina.extract_text()
                if not texto:
                    continue
            except:
                continue

            linhas = texto.split("\n")

            for linha in linhas:
                linha_lower = linha.lower()

                if linha.strip().startswith("Associado"):
                    partes = linha.split(":")
                    if len(partes) > 1:
                        nome_limpo = partes[1].split("Categoria")[0].strip()
                        associado_atual = nome_limpo
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

    # converter set para list
    for nome in dados:
        dados[nome]["faltas"] = list(dados[nome]["faltas"])
        dados[nome]["afastamentos"] = list(dados[nome]["afastamentos"])

    return dados


@app.route("/", methods=["GET", "POST"])
def home():
    resultado = None
    dados = {}

    if request.method == "POST":
        try:
            if "file" not in request.files:
                return "Erro: nenhum arquivo enviado"

            file = request.files["file"]

            if file.filename == "":
                return "Erro: selecione um PDF"

            # 🔥 evita erro com PDF grande
            file.stream.seek(0)

            dados = analisar_pdf(file)

            mostrar_faltas = request.form.get("mostrar_faltas")
            mostrar_afastamentos = request.form.get("mostrar_afastamentos")

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

        except Exception as e:
            return f"Erro ao processar o PDF: {str(e)}"

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
