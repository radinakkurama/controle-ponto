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
            width: 420px;
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

        input[type="file"] {
            margin-bottom: 10px;
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
        <input type="file" name="file" required><br>

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
    let d = await res.json();

    if(d.status === "done"){
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
    } else {
        document.getElementById("status").innerText = "❌ Erro: " + d.erro;
    }
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


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]

    filepath = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
    file.save(filepath)

    try:
        resultado = analisar_pdf(filepath)
        return jsonify({
            "status": "done",
            "dados": resultado
        })
    except Exception as e:
        return jsonify({
            "status": "erro",
            "erro": str(e)
        })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
