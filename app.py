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
            font-family: 'Segoe UI', Tahoma;
            background: linear-gradient(135deg, #667eea, #764ba2);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }

        .container {
            background: white;
            padding: 30px;
            border-radius: 16px;
            width: 450px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.2);
            text-align: center;
        }

        h2 {
            margin-bottom: 20px;
        }

        input[type="file"] {
            margin-bottom: 15px;
        }

        .filters {
            margin-bottom: 15px;
        }

        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
        }

        button:hover {
            background: #5a67d8;
        }

        #status {
            margin-top: 15px;
            font-weight: bold;
        }

        .resultado {
            margin-top: 20px;
            text-align: left;
            white-space: pre-wrap;
            max-height: 300px;
            overflow-y: auto;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }
    </style>
</head>
<body>

<div class="container">
    <h2>📊 Controle de Ponto</h2>

    <form id="form">
        <input type="file" name="file" required><br>

        <div class="filters">
            <label><input type="checkbox" id="faltas" checked> Faltas</label>
            <label><input type="checkbox" id="afast" checked> Afastamentos</label>
        </div>

        <button type="submit">Analisar PDF</button>
    </form>

    <div id="status"></div>
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
        document.getElementById("status").innerText = "❌ Erro";
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
