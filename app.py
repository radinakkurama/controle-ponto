from flask import Flask, request, jsonify, render_template_string
import pdfplumber
import re
import threading
import uuid
import os

app = Flask(__name__)

processos = {}

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Controle de Ponto</title>
    <style>
        body {
            font-family: Arial;
            background: linear-gradient(120deg, #4facfe, #00f2fe);
            text-align: center;
            padding: 30px;
        }

        .card {
            background: white;
            padding: 30px;
            border-radius: 12px;
            width: 400px;
            margin: auto;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        button {
            background: #4facfe;
            border: none;
            padding: 10px 20px;
            color: white;
            border-radius: 6px;
            cursor: pointer;
        }

        .resultado {
            margin-top: 20px;
            text-align: left;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>

<div class="card">
    <h2>📊 Controle de Ponto</h2>

    <form id="form">
        <input type="file" name="file"><br><br>

        <label><input type="checkbox" id="faltas" checked> Faltas</label>
        <label><input type="checkbox" id="afast" checked> Afastamentos</label>

        <br><br>
        <button type="submit">Analisar</button>
    </form>

    <p id="status"></p>
    <div class="resultado" id="resultado"></div>
</div>

<script>
document.getElementById("form").onsubmit = async function(e){
    e.preventDefault();

    let formData = new FormData(this);

    document.getElementById("status").innerText = "⏳ Processando...";
    document.getElementById("resultado").innerText = "";

    let res = await fetch("/upload", { method:"POST", body: formData });
    let data = await res.json();

    let id = data.id;

    let intervalo = setInterval(async () => {
        let r = await fetch("/status/" + id);
        let d = await r.json();

        if(d.status === "done"){
            clearInterval(intervalo);

            document.getElementById("status").innerText = "✅ Concluído";

            let mostrarFaltas = document.getElementById("faltas").checked;
            let mostrarAfast = document.getElementById("afast").checked;

            let texto = "";

            d.dados.forEach(p => {

                if (!p.faltas.length && !p.afastamentos.length) return;

                texto += "👤 " + p.nome + "\\n\\n";

                if (mostrarFaltas){
                    texto += "❌ Faltas: " + p.faltas.length + "\\n";
                    p.faltas.forEach(f => texto += "• " + f + "\\n");
                }

                if (mostrarAfast){
                    texto += "\\n🏥 Afastamentos: " + p.afastamentos.length + "\\n";
                    p.afastamentos.forEach(a => texto += "• " + a + "\\n");
                }

                texto += "\\n------------------------\\n\\n";
            });

            document.getElementById("resultado").innerText = texto;
        }
    }, 2000);
}
</script>

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

                if "associado" in linha_lower:
                    partes = linha.split(":")
                    if len(partes) > 1:
                        nome = partes[1].split("Categoria")[0].strip()
                        associado_atual = nome

                        if nome not in dados:
                            dados[nome] = {"faltas": [], "afastamentos": []}

                if not associado_atual:
                    continue

                data_match = re.search(r"\\d{2}/\\d{2}/\\d{2}", linha)
                if not data_match:
                    continue

                data = data_match.group()

                if "falta injustificada" in linha_lower:
                    if data not in dados[associado_atual]["faltas"]:
                        dados[associado_atual]["faltas"].append(data)

                if "afast doenca" in linha_lower:
                    if data not in dados[associado_atual]["afastamentos"]:
                        dados[associado_atual]["afastamentos"].append(data)

    resultado = []

    for nome, info in dados.items():
        if not info["faltas"] and not info["afastamentos"]:
            continue

        resultado.append({
            "nome": nome,
            "faltas": info["faltas"],
            "afastamentos": info["afastamentos"]
        })

    return resultado


def processar_em_background(filepath, job_id):
    try:
        resultado = analisar_pdf(filepath)
        processos[job_id] = {"status": "done", "dados": resultado}
    except Exception as e:
        processos[job_id] = {"status": "erro", "dados": str(e)}


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]

    job_id = str(uuid.uuid4())
    filepath = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")

    file.save(filepath)

    processos[job_id] = {"status": "processing"}

    thread = threading.Thread(
        target=processar_em_background,
        args=(filepath, job_id)
    )
    thread.start()

    return jsonify({"id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    return jsonify(processos.get(job_id, {"status": "not_found"}))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
