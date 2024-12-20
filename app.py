from doctest import debug

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from login_manager import login_manager, auth
from config.database import initialize_mysql
from veiculo import veiculo
from sms_sender import sms_sender
from user import user
from promoter import promoter
from admin import admin
from datetime import datetime, timedelta

app = Flask(__name__)

# configuration
app.secret_key = 'db_secret'

# init apps
mysql = initialize_mysql(app)
login_manager.init_app(app)

# register blueprints
app.register_blueprint(auth)
app.register_blueprint(veiculo)
app.register_blueprint(user)
app.register_blueprint(sms_sender)
app.register_blueprint(promoter)
app.register_blueprint(admin)


def atualizar_status():
    try:
        # Conectar ao banco de dados
        with app.app_context():
            cur = mysql.connection.cursor()

            # Obter a data atual
            now = datetime.now()
            expiration = now - timedelta(minutes=45)

            # Consulta SQL para atualizar o status
            cur.execute("UPDATE Locacao SET status = 'VENCIDO' WHERE data_inicio < %s AND status = 'ALOCADO' ",
                        (expiration,))

            mysql.connection.commit()

            # Fechar o cursor
            cur.close()

            print('Status atualizado com sucesso.' + now.strftime('%Y-%m-%d %H:%M:%S'))

    except Exception as e:
        print(str(e))


# Configuração do agendador de tarefas
scheduler = BackgroundScheduler()
scheduler.add_job(atualizar_status, 'interval', minutes=5)
scheduler.start()

def main():
    context = ('static/certificate.crt', 'static/privateKey.key')
    app.run(host='0.0.0.0', ssl_context=context)

if __name__ == '__main__':
    main()