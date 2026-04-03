from flask import Flask, request, render_template_string, jsonify
import pdfplumber
import re
import threading
import uuid

app = Flask(__name__)

processos = {}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Controle de Ponto</title>
</head>
<body style="font-family: Arial; text-align:center;">

<h2>📊 Controle de Ponto</h2>

<form id="form">
    <input type="file" name="file"><br><br>
    <button type="submit">Analisar</button>
</form>

<p id="status"></p>
<pre id="resultado"></pre>

<script>
document.getElementById("form").onsubmit = async function(e){
    e.preventDefault();

    let formData = new FormData(this);

    document.getElementById("status").innerText = "⏳ Processando...";

    let res = await fetch("/upload", { method:"POST", body: formData });
    let data = await res.json();

    let id = data.id;

    let intervalo = setInterval(async () => {
        let r = await fetch("/status/" + id);
        let d = await r.json();

        if(d.status === "done"){
            clearInterval(intervalo);
            document.getElementById("status").innerText = "✅ Concluído";
            document.getElementById("resultado").innerText = d.resultado;
        }
    }, 2000);
}
</script>

</body>
</html>
"""

def analisar_pdf(file):
    dados = {}
    associado_atual = None

    with pdfplumber.open(file) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            for linha in texto.split("\n"):
                linha_lower = linha.lower()

                if "associado" in linha_lower:
                    partes = linha.split(":")
                    if len(partes) > 1:
                        nome = partes[1].split("Categoria")[0].strip()
                        associado_atual = nome

                        if nome not in dados:
                            dados[nome] = {"faltas": [], "afastamentos": []}

                if not associado_atual:
                    continue

                data_match = re.search(r"\d{2}/\d{2}/\d{2}", linha)
                if not data_match:
                    continue

                data = data_match.group()

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

        resultado += f"👤 {nome}\n\n"

        resultado += f"❌ Faltas: {len(info['faltas'])}\n"
        for d in info["faltas"]:
            resultado += f"• {d}\n"

        resultado += f"\n🏥 Afastamentos: {len(info['afastamentos'])}\n"
        for d in info["afastamentos"]:
            resultado += f"• {d}\n"

        resultado += "\n" + "-"*40 + "\n\n"

    return resultado


def processar_em_background(file, job_id):
    try:
        resultado = analisar_pdf(file)
        processos[job_id] = {"status": "done", "resultado": resultado}
    except Exception as e:
        processos[job_id] = {"status": "erro", "resultado": str(e)}


@app.route("/")
def home():
    return HTML


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]

    job_id = str(uuid.uuid4())

    processos[job_id] = {"status": "processing"}

    thread = threading.Thread(target=processar_em_background, args=(file, job_id))
    thread.start()

    return jsonify({"id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    return jsonify(processos.get(job_id, {"status": "not_found"}))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
