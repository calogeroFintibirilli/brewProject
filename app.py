
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from bson import ObjectId
import json
from flask_socketio import SocketIO, emit
import random
import threading
from flask_mqtt import Mqtt
import time


import os

app = Flask(__name__)
app.secret_key = 'chiave_segreta_per_flash'
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['UPLOAD_FOLDER'] = 'static/uploads'


# ---------------- MQTT CONFIG ----------------
app.config['MQTT_BROKER_URL'] = 'localhost'
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_KEEPALIVE'] = 60
app.config['MQTT_TLS_ENABLED'] = False

mqtt = Mqtt(app)
last_values = {
    "TT01": None,
    "TT02": None,
    "TT03": None
}

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

    ricette = list(ricette_coll.find({
        "$or": [
            {"archiviata": {"$exists": False}},
            {"archiviata": False}
        ]
    }))
    total = ricette_coll.count_documents({
        "$or": [
            {"archiviata": {"$exists": False}},
            {"archiviata": False}
        ]
    })

    client.close()
    return render_template('index.html', ricette=ricette, total=total)

@app.route('/elimina/<ricetta_id>', methods=['POST'])
def elimina_ricetta(ricetta_id):
    client = connect_to_mongodb()
    db = client['mio_database']
    ricette_coll = db['ricette']
    esecuzioni_coll = db['esecuzioni']

    in_uso = esecuzioni_coll.count_documents({"ricetta_id": ObjectId(ricetta_id)}) > 0
    conferma = request.form.get("conferma", "no")

    if in_uso and conferma == "no":
        ricetta = ricette_coll.find_one({"_id": ObjectId(ricetta_id)})
        client.close()
        return render_template("conferma_elimina.html", ricetta=ricetta)

    if in_uso and conferma == "si":
        ricette_coll.update_one(
            {"_id": ObjectId(ricetta_id)},
            {"$set": {"archiviata": True}}
        )
        flash("📦 Ricetta archiviata (non eliminata definitivamente).")
        client.close()
        return redirect(url_for('index'))

    ricette_coll.delete_one({"_id": ObjectId(ricetta_id)})
    flash("✅ Ricetta eliminata definitivamente.")
    client.close()
    return redirect(url_for('index'))

@app.route('/aggiungi', methods=['GET', 'POST'])
def aggiungi_ricetta():
    client = connect_to_mongodb()
    db = client['mio_database']
    ricette_coll = db['ricette']

    if request.method == 'POST':
        nome = request.form['nome']
        stile = request.form.get('stile')
        abv = float(request.form.get('abv', 0) or 0)
        ibu = int(request.form.get('ibu', 0) or 0)

        ingredienti_json = request.form.get('ingredienti_json', '[]')
        try:
            ingredienti = json.loads(ingredienti_json)
        except json.JSONDecodeError:
            ingredienti = []
            flash("Errore nella lettura degli ingredienti.", "error")

        fasi_json = request.form.get('fasi_json', '[]')
        try:
            fasi = json.loads(fasi_json)
        except json.JSONDecodeError:
            fasi = []
            flash("Errore nella lettura delle fasi di produzione.", "error")

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
            "fasi": fasi,
            "note": note,
            "foto": foto_filename,
            "data_creazione": datetime.now()
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

    fasi_esecuzione = []
    for fase in ricetta.get("fasi", []):
        fasi_esecuzione.append({
            "numero": fase["numero"],
            "descrizione": fase["descrizione"],
            "durata_minuti": fase.get("durata_minuti", 0),
            "completata": False,
            "data_inizio": None,
            "data_fine": None,
            "note": ""  # campo note per fase
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

        fasi_norm = []
        for f in e.get("fasi", []):
            data_inizio_f = f.get("data_inizio")
            data_fine_f = f.get("data_fine")

            # Se sono datetime li formatto, se sono già stringhe li lascio
            if isinstance(data_inizio_f, datetime):
                data_inizio_str = data_inizio_f.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                data_inizio_str = data_inizio_f or ""

            if isinstance(data_fine_f, datetime):
                data_fine_str = data_fine_f.strftime('%Y-%m-%dT%H:%M:%S')
            else:
                data_fine_str = data_fine_f or ""

            fasi_norm.append({
                "numero": f.get("numero"),
                "descrizione": f.get("descrizione", ""),
                "durata_minuti": int(f.get("durata_minuti", 0)) if f.get("durata_minuti") else 0,
                "completata": bool(f.get("completata", False)),
                "data_inizio": data_inizio_str,
                "data_fine": data_fine_str,
                "note": f.get("note", "")
            })

        data_inizio_esec = e.get("data_inizio")
        if isinstance(data_inizio_esec, datetime):
            data_inizio_esec_str = data_inizio_esec.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            data_inizio_esec_str = data_inizio_esec or ""

        result.append({
            "id": str(e["_id"]),
            "nome_ricetta": ricetta["nome"] if ricetta else "Sconosciuta",
            "foto": ricetta.get("foto") if ricetta else None,
            "data_inizio": data_inizio_esec_str,
            "note": e.get("note", ""),
            "stato": e.get("stato", "N/D"),
            "fasi": fasi_norm,
            "fase_corrente": int(e.get("fase_corrente", 1)),
        })

    client.close()
    return render_template('in_corso.html', esecuzioni=result)


@app.route('/dettaglio/<esecuzione_id>')
def dettaglio_lavorazione(esecuzione_id):
    """Pagina di dettaglio per una produzione in corso."""
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    ricette_coll = db['ricette']

    e = esecuzioni_coll.find_one({"_id": ObjectId(esecuzione_id)})
    if not e:
        flash("Produzione non trovata.")
        client.close()
        return redirect(url_for('in_corso'))

    ricetta = ricette_coll.find_one({"_id": e["ricetta_id"]})

    # Normalizza i dati come per /in-corso
    fasi_norm = []
    for f in e.get("fasi", []):
        data_inizio = f.get("data_inizio")
        data_fine = f.get("data_fine")

        if isinstance(data_inizio, datetime):
            data_inizio = data_inizio.strftime('%Y-%m-%dT%H:%M:%SZ')
        if isinstance(data_fine, datetime):
            data_fine = data_fine.strftime('%Y-%m-%dT%H:%M:%S')

        fasi_norm.append({
            "numero": f.get("numero"),
            "descrizione": f.get("descrizione", ""),
            "durata_minuti": f.get("durata_minuti", 0),
            "completata": f.get("completata", False),
            "data_inizio": data_inizio,
            "data_fine": data_fine,
            "note": f.get("note", "")
        })

    lavorazione = {
        "id": str(e["_id"]),
        "nome_ricetta": ricetta["nome"] if ricetta else "Sconosciuta",
        "foto": ricetta.get("foto") if ricetta else None,
        "data_inizio": e.get("data_inizio").strftime("%Y-%m-%dT%H:%M:%S") if e.get("data_inizio") else "N/D",
        "note": e.get("note", ""),
        "stato": e.get("stato", "N/D"),
        "fasi": fasi_norm,
        "fase_corrente": e.get("fase_corrente", 1)
    }

    client.close()
    return render_template("dettaglio_lavorazione.html", lavorazione=lavorazione)
@app.route('/storico')
def storico():
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    ricette_coll = db['ricette']

    nome_ricetta = request.args.get('nome_ricetta', '').strip()
    data_filtro = request.args.get('data', '').strip()

    query = {"stato": "Completata"}
    if nome_ricetta:
        ricetta = ricette_coll.find_one({"nome": {"$regex": nome_ricetta, "$options": "i"}})
        if ricetta:
            query["ricetta_id"] = ricetta["_id"]
        else:
            query["ricetta_id"] = None

    if data_filtro:
        try:
            data_obj = datetime.strptime(data_filtro, "%Y-%m-%d")
            giorno_successivo = data_obj + timedelta(days=1)
            query["data_inizio"] = {"$gte": data_obj, "$lt": giorno_successivo}
        except ValueError:
            pass

    esecuzioni = list(esecuzioni_coll.find(query).sort("data_fine", -1))
    result = []
    for e in esecuzioni:
        ricetta = ricette_coll.find_one({"_id": e["ricetta_id"]})
        result.append({
            "id": str(e["_id"]),
            "nome_ricetta": ricetta["nome"] if ricetta else "Sconosciuta",
            "foto": ricetta.get("foto") if ricetta else None,
            "data_inizio": e.get("data_inizio").strftime("%Y-%m-%d %H:%M") if e.get("data_inizio") else "N/D",
            "data_fine": e.get("data_fine").strftime("%Y-%m-%d %H:%M") if e.get("data_fine") else "N/D",
        })

    client.close()
    return render_template('storico.html', esecuzioni=result, nome_ricetta=nome_ricetta, data_filtro=data_filtro)


@app.route('/storico/<esecuzione_id>')
def dettaglio_storico(esecuzione_id):
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']
    ricette_coll = db['ricette']

    e = esecuzioni_coll.find_one({"_id": ObjectId(esecuzione_id)})
    if not e:
        flash("Esecuzione non trovata.")
        return redirect(url_for('storico'))

    ricetta = ricette_coll.find_one({"_id": e["ricetta_id"]})

    # calcolo KPI base
    durata = None
    if e.get("data_inizio") and e.get("data_fine"):
        durata = (e["data_fine"] - e["data_inizio"]).total_seconds() / 3600  # ore

    kpi = {
        "durata_ore": round(durata, 2) if durata else None,
        "num_fasi": len(e.get("fasi", [])),
        "note": len([f for f in e.get("fasi", []) if f.get("note")]),
    }

    data = {
        "id": str(e["_id"]),
        "nome_ricetta": ricetta["nome"] if ricetta else "Sconosciuta",
        "foto": ricetta.get("foto") if ricetta else None,
        "data_inizio": e.get("data_inizio").strftime("%Y-%m-%d %H:%M") if e.get("data_inizio") else "N/D",
        "data_fine": e.get("data_fine").strftime("%Y-%m-%d %H:%M") if e.get("data_fine") else "N/D",
        "note": e.get("note", ""),
        "fasi": e.get("fasi", []),
        "kpi": kpi
    }

    client.close()
    return render_template('storico_dettaglio.html', esecuzione=data)


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
                "fasi.$.data_inizio": datetime.utcnow(),
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

    esecuzione = esecuzioni_coll.find_one({"_id": ObjectId(esecuzione_id)})
    if esecuzione and fase_numero < len(esecuzione["fasi"]):
        esecuzioni_coll.update_one(
            {"_id": ObjectId(esecuzione_id)},
            {"$set": {"fase_corrente": fase_numero + 1}}
        )
    else:
        esecuzioni_coll.update_one(
            {"_id": ObjectId(esecuzione_id)},
            {"$set": {
                "stato": "Completata",
                "data_fine": datetime.now()
            }}
        )

    client.close()
    return jsonify({"success": True})

# ✅ NUOVO: salvataggio note per singola fase
@app.route('/fase/<esecuzione_id>/<int:fase_numero>/note', methods=['POST'])
def save_fase_note(esecuzione_id, fase_numero):
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']

    data = request.get_json(silent=True) or {}
    nota = data.get("note", "")

    res = esecuzioni_coll.update_one(
        {"_id": ObjectId(esecuzione_id), "fasi.numero": fase_numero},
        {"$set": {"fasi.$.note": nota}}
    )

    client.close()

    if res.matched_count:
        return jsonify(success=True)
    return jsonify(success=False), 404

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

    for fase in result["fasi"]:
        if isinstance(fase.get("data_inizio"), datetime):
            fase["data_inizio"] = fase["data_inizio"].isoformat()
        if isinstance(fase.get("data_fine"), datetime):
            fase["data_fine"] = fase["data_fine"].isoformat()

    esecuzione_json = json.dumps(result)

    client.close()
    return render_template('dettaglio_esecuzione.html', esecuzione=result, esecuzione_json=esecuzione_json)

@app.route('/storico_ricette')
def storico_ricette():
    client = connect_to_mongodb()
    db = client['mio_database']
    ricette_coll = db['ricette']

    archiviate = list(ricette_coll.find({"archiviata": True}))
    total = ricette_coll.count_documents({"archiviata": True})

    client.close()
    return render_template('storico_ricette.html', ricette=archiviate, total=total)

@app.route('/produzione/<esecuzione_id>/commento', methods=['POST'])
def add_commento(esecuzione_id):
    client = connect_to_mongodb()
    db = client['mio_database']
    esecuzioni_coll = db['esecuzioni']

    data = request.get_json(silent=True) or {}
    testo = data.get("testo", "").strip()
    if not testo:
        client.close()
        return jsonify(success=False, error="Testo vuoto"), 400

    commento = {
        "utente": "Operatore",
        "testo": testo,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    res = esecuzioni_coll.update_one(
        {"_id": ObjectId(esecuzione_id)},
        {"$push": {"commenti": {"$each": [commento], "$position": 0}}}
    )

    client.close()
    if res.matched_count:
        return jsonify(success=True, comment=commento)
    return jsonify(success=False), 404


# ---------------- MQTT CALLBACKS ----------------
@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    print("MQTT Connesso con codice:", rc)

    # Iscrizione a tutti i sensori
    mqtt.subscribe("sensori/TT01")
    mqtt.subscribe("sensori/TT02")
    mqtt.subscribe("sensori/TT03")
    print("Iscritto ai topic sensori/*")

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    topic = message.topic
    value = message.payload.decode()

    print(f"[MQTT] Ricevuto {value} da {topic}")

    # Estraggo nome sonda dal topic
    sensor_id = topic.split("/")[-1]

    # Salvo l'ultimo valore
    last_values[sensor_id] = value

    # Invio ai client collegati via SocketIO
    socketio.emit("sensor_update", {
        "sensor": sensor_id,
        "value": value
    }, namespace="/sensori")

# --- HANDLER CONNESSIONE ---
@socketio.on('connect', namespace='/sensori')
def on_connect():
    print("✅ Client connesso al canale /sensori")

# --- AVVIO THREAD DI BACKGROUND IN SICUREZZA ---
#socketio.start_background_task(sensori_background_thread)


if __name__ == "__main__":
      socketio.run(app, host="0.0.0.0", port=5000, debug=True)
