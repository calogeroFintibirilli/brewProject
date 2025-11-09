from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from bson import ObjectId
import os

app = Flask(__name__)
app.secret_key = 'chiave_segreta_per_flash'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

def connect_to_mongodb():
    mongo_host = os.getenv('MONGO_HOST', 'mongodb')
    mongo_port = int(os.getenv('MONGO_PORT', 27017))
    mongo_user = os.getenv('MONGO_USER', 'admin')
    mongo_password = os.getenv('MONGO_PASSWORD', 'password123')
    client = MongoClient(
        host=mongo_host,
        port=mongo_port,
        username=mongo_user,
        password=mongo_password,
        authSource='admin'
    )
    client.server_info()
    return client

@app.route('/')
def index():
    client = connect_to_mongodb()
    db = client['mio_database']
    ricette_coll = db['ricette']
    ricette = list(ricette_coll.find())
    total = ricette_coll.count_documents({})
    client.close()
    return render_template('index.html', ricette=ricette, total=total)

@app.route('/aggiungi', methods=['GET', 'POST'])
def aggiungi_ricetta():
    client = connect_to_mongodb()
    db = client['mio_database']
    ricette_coll = db['ricette']

    if request.method == 'POST':
        nome = request.form['nome']
        stile = request.form.get('stile')
        abv = float(request.form.get('abv', 0))
        ibu = int(request.form.get('ibu', 0))
        
        # Parsing ingredienti
        ingredienti = []
        for line in request.form['ingredienti'].strip().split('\n'):
            if ':' in line:
                nome_ing, quant_unita = line.split(':', 1)
                parts = quant_unita.strip().split()
                if len(parts) >= 2:
                    quant = float(parts[0])
                    unita = ' '.join(parts[1:])
                    ingredienti.append({"nome": nome_ing.strip(), "quantita": quant, "unita": unita})
        
        # Parsing fasi da JSON
        import json
        fasi_json = request.form.get('fasi_json', '[]')
        fasi = json.loads(fasi_json) if fasi_json else []
        
        note = request.form.get('note', '')

        foto_filename = None
        if 'foto' in request.files:
            foto = request.files['foto']
            if foto.filename:
                foto_filename = secure_filename(foto.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], foto_filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                foto.save(path)

        ricetta = {
            "nome": nome,
            "stile": stile,
            "abv": abv,
            "ibu": ibu,
            "ingredienti": ingredienti,
            "fasi": fasi,  # Sostituisce "istruzioni"
            "note": note,
            "foto": foto_filename
        }

        ricette_coll.insert_one(ricetta)
        flash(f'Ricetta "{nome}" aggiunta con successo!')
        client.close()
        return redirect(url_for('index'))

    client.close()
    return render_template('aggiungi.html')

@app.route('/esegui/<ricetta_id>', methods=['POST'])
def esegui_ricetta(ricetta_id):
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    ricette_coll = db['ricette']
    ricetta = ricette_coll.find_one({"_id": ObjectId(ricetta_id)})
    if not ricetta:
        flash('Ricetta non trovata!')
        client.close()
        return redirect(url_for('index'))

    # Crea fasi per l'esecuzione
    fasi_esecuzione = []
    for fase in ricetta.get("fasi", []):
        fasi_esecuzione.append({
            "numero": fase["numero"],
            "descrizione": fase["descrizione"],
            "durata_minuti": fase.get("durata_minuti", 0),
            "completata": False,
            "data_inizio": None,
            "data_fine": None
        })

    esecuzione = {
        "ricetta_id": ObjectId(ricetta_id),
        "data_inizio": datetime.now(),
        "data_fine": None,
        "stato": "In Corso",
        "fasi": fasi_esecuzione,
        "fase_corrente": 1,
        "note": request.form.get('note_esecuzione', '')
    }
    esecuzioni_coll.insert_one(esecuzione)
    flash('Esecuzione avviata con successo!')
    client.close()
    return redirect(url_for('in_corso'))

@app.route('/in-corso')
def in_corso():
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    ricette_coll = db['ricette']

    esecuzioni = list(esecuzioni_coll.find({"stato": "In Corso"}).sort("data_inizio", -1))
    result = []
    for e in esecuzioni:
        ricetta = ricette_coll.find_one({"_id": e["ricetta_id"]})
        result.append({
            "id": str(e["_id"]),
            "nome_ricetta": ricetta["nome"] if ricetta else "Sconosciuta",
            "foto": ricetta.get("foto") if ricetta else None,
            "data_inizio": e["data_inizio"].isoformat() if "data_inizio" in e else None,
            "note": e.get("note", ""),
            "stato": e.get("stato", "N/D"),
            "fasi": e.get("fasi", []),
            "fase_corrente": e.get("fase_corrente", 1)
        })
    client.close()
    return render_template('in_corso.html', esecuzioni=result)

@app.route('/storico')
def storico():
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    ricette_coll = db['ricette']

    esecuzioni = list(esecuzioni_coll.find({"stato": "Completata"}).sort("data_fine", -1))
    result = []
    for e in esecuzioni:
        ricetta = ricette_coll.find_one({"_id": e["ricetta_id"]})
        result.append({
            "id": str(e["_id"]),
            "nome_ricetta": ricetta["nome"] if ricetta else "Sconosciuta",
            "foto": ricetta.get("foto") if ricetta else None,
            "data_inizio": e["data_inizio"].isoformat() if "data_inizio" in e else None,
            "data_fine": e["data_fine"].isoformat() if "data_fine" in e else None,
            "note": e.get("note", ""),
            "stato": e.get("stato", "N/D")
        })
    client.close()
    return render_template('storico.html', esecuzioni=result)

@app.route('/termina/<esecuzione_id>', methods=['POST'])
def termina_esecuzione(esecuzione_id):
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    
    esecuzioni_coll.update_one(
        {"_id": ObjectId(esecuzione_id)},
        {
            "$set": {
                "stato": "Completata",
                "data_fine": datetime.now()
            }
        }
    )
    flash('Esecuzione completata con successo!')
    client.close()
    return redirect(url_for('in_corso'))

@app.route('/fase/<esecuzione_id>/<int:fase_numero>/start', methods=['POST'])
def start_fase(esecuzione_id, fase_numero):
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    
    esecuzioni_coll.update_one(
        {"_id": ObjectId(esecuzione_id), "fasi.numero": fase_numero},
        {
            "$set": {
                "fasi.$.data_inizio": datetime.now(),
                "fase_corrente": fase_numero
            }
        }
    )
    client.close()
    return jsonify({"success": True})

@app.route('/fase/<esecuzione_id>/<int:fase_numero>/complete', methods=['POST'])
def complete_fase(esecuzione_id, fase_numero):
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    
    esecuzioni_coll.update_one(
        {"_id": ObjectId(esecuzione_id), "fasi.numero": fase_numero},
        {
            "$set": {
                "fasi.$.completata": True,
                "fasi.$.data_fine": datetime.now()
            }
        }
    )
    client.close()
    return jsonify({"success": True})

@app.route('/esecuzione/<esecuzione_id>')
def dettaglio_esecuzione(esecuzione_id):
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    ricette_coll = db['ricette']
    
    esecuzione = esecuzioni_coll.find_one({"_id": ObjectId(esecuzione_id)})
    if not esecuzione:
        flash('Esecuzione non trovata!')
        client.close()
        return redirect(url_for('in_corso'))
    
    ricetta = ricette_coll.find_one({"_id": esecuzione["ricetta_id"]})
    
    result = {
        "id": str(esecuzione["_id"]),
        "nome_ricetta": ricetta["nome"] if ricetta else "Sconosciuta",
        "foto": ricetta.get("foto") if ricetta else None,
        "data_inizio": esecuzione["data_inizio"].isoformat() if "data_inizio" in esecuzione else None,
        "data_fine": esecuzione.get("data_fine").isoformat() if esecuzione.get("data_fine") else None,
        "note": esecuzione.get("note", ""),
        "stato": esecuzione.get("stato", "N/D"),
        "fasi": esecuzione.get("fasi", []),
        "fase_corrente": esecuzione.get("fase_corrente", 1)
    }
    
    # Converti datetime in ISO format per fasi
    for fase in result["fasi"]:
        if fase.get("data_inizio"):
            fase["data_inizio"] = fase["data_inizio"].isoformat()
        if fase.get("data_fine"):
            fase["data_fine"] = fase["data_fine"].isoformat()
    
    import json
    esecuzione_json = json.dumps(result)
    
    client.close()
    return render_template('dettaglio_esecuzione.html', esecuzione=result, esecuzione_json=esecuzione_json)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)