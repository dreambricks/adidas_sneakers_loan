import csv
import base64
from datetime import datetime, timedelta
from fileinput import filename

from flask import Blueprint, request, session, redirect, url_for, render_template, make_response, send_file, jsonify

from config.database import mysql
import json
import pandas as pd
from io import BytesIO

admin = Blueprint('admin', __name__)


@admin.route('/admin/login', methods=['POST', 'GET'])
def admin_login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM Promotor WHERE usuario = %s AND senha = %s", (username, password))
        promotor = cur.fetchone()
        cur.close()

        if promotor and promotor[1] == 'admin':
            session['logged_in'] = True
            session['admin_id'] = promotor[0]
            return redirect(url_for('admin.admin_menu_page'))
        else:
            return redirect(url_for('admin.admin_login_page'))

    return render_template('admin/1-admin-login.html')


@admin.route('/admin/menu')
def admin_menu_page():
    if 'logged_in' in session and session['logged_in']:
        return render_template('admin/2-admin-menu.html')
    else:
        return redirect(url_for('admin.admin_login_page'))

@admin.route('/admin/menu/admin')
def admin_menu_admin_page():
    if 'logged_in' in session and session['logged_in']:
        return render_template('admin/7-admin-menu-admin.html')
    else:
        return redirect(url_for('admin.admin_login_page'))


@admin.route('/admin/stock')
def stock_page():
    if 'logged_in' in session and session['logged_in']:
        return render_template('promoter/4-available-shoes.html')
    else:
        return redirect(url_for('admin.admin_login_page'))

@admin.route('/admin/dashboard')
def dashboard_page():
    if 'logged_in' in session and session['logged_in']:
        return render_template('admin/8-dashboard.html')
    else:
        return redirect(url_for('admin.admin_login_page'))


@admin.route('/admin/statistics/total', methods=['GET', 'POST'])
def statistics_page():
    cur = mysql.connection.cursor()

    # Ajusta o limite do GROUP_CONCAT para evitar truncamentos
    cur.execute("SET SESSION group_concat_max_len = 10000;")

    # Gerar dinamicamente a lista de colunas SUM(CASE WHEN ...)
    cur.execute("""
        SELECT GROUP_CONCAT(
            CONCAT(
                'SUM(CASE WHEN Modelo.nome = "', nome, '" THEN 1 ELSE 0 END) AS `', REPLACE(nome, '`', ''), '`'
            )
        ) 
        FROM Modelo
    """)

    colunas_sum_case = cur.fetchone()[0]

    # Verifica se a string de colunas geradas é válida
    if not colunas_sum_case:
        colunas_sum_case = "0 AS `No Data`"  # Evita erro caso não haja modelos

    # Construir query final dinamicamente
    sql = f"""
        SELECT 
            DATE_FORMAT(Locacao.data_inicio, "%y-%m-%d") AS bdate, 
            Veiculo.nome AS nome_veiculo, 
            {colunas_sum_case}, 
            COUNT(1) AS total
        FROM 
            Locacao
        JOIN 
            Veiculo ON Locacao.Veiculo = Veiculo.id
        JOIN 
            Tenis ON Locacao.Tenis = Tenis.id
        JOIN 
            Modelo ON Tenis.Modelo = Modelo.id
        GROUP BY 
            DATE_FORMAT(Locacao.data_inicio, "%y-%m-%d"), Veiculo.nome
        ORDER BY 
            DATE_FORMAT(Locacao.data_inicio, "%y-%m-%d") DESC, Veiculo.nome DESC;
    """

    # Executar a query dinâmica
    cur.execute(sql)
    rentals = cur.fetchall()
    fieldnames = [i[0] for i in cur.description]  # Obter os nomes das colunas dinamicamente
    if request.method == 'POST':
        now = datetime.now().strftime('%Y-%m-%d')
        filename = f'{now}_estatisticas_modelo.xlsx'

        df = pd.DataFrame(rentals, columns=fieldnames)

        # Converter a data para o formato dd/mm/aaaa
        if 'bdate' in df.columns:
            df['bdate'] = pd.to_datetime(df['bdate'], format='%y-%m-%d').dt.strftime('%d/%m/%Y')

        # Criando um arquivo Excel na memória
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Estatísticas Totais")
        output.seek(0)

        cur.close()
        return send_file(output, download_name=filename, as_attachment=True,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    cur.close()
    return render_template('admin/3-statistics-total.html', rentals=rentals, fieldnames=fieldnames)


@admin.route('/admin/statistics/status', methods=['GET', 'POST'])
def statistics_status_page():
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT 
            date_format(Locacao.data_inicio, "%y-%m-%d") AS bdate, 
            Veiculo.nome AS nome_veiculo,
            SUM(CASE WHEN Locacao.status = 'DEVOLVIDO' THEN 1 ELSE 0 END) AS 'DEVOLVIDO',
            SUM(CASE WHEN Locacao.status = 'CANCELADO' THEN 1 ELSE 0 END) AS 'CANCELADO',
            SUM(CASE WHEN Locacao.status = 'VENCIDO' THEN 1 ELSE 0 END) AS 'VENCIDO',
            COUNT(1) AS total
        FROM 
            Locacao
        JOIN 
            Veiculo ON Locacao.Veiculo = Veiculo.id
        GROUP BY 
            date_format(Locacao.data_inicio, "%y-%m-%d"), Veiculo.nome
        ORDER BY 
            date_format(Locacao.data_inicio, "%y-%m-%d") DESC, Veiculo.nome DESC;
        """
    )

    rentals = cur.fetchall()
    fieldnames = [i[0] for i in cur.description]

    if request.method == 'POST':
        now = datetime.now().strftime('%Y-%m-%d')
        filename = f'{now}_estatisticas_status.xlsx'

        df = pd.DataFrame(rentals, columns=fieldnames)

        # Converter a data para o formato dd/mm/aaaa
        if 'bdate' in df.columns:
            df['bdate'] = pd.to_datetime(df['bdate'], format='%y-%m-%d').dt.strftime('%d/%m/%Y')

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Estatísticas Status")
        output.seek(0)

        cur.close()
        return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    cur.close()
    return render_template('admin/3-statistics-status.html', rentals=rentals)



@admin.route('/admin/statistics/gen', methods=['GET', 'POST'])
def statistics_gen_page():
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT 
            date_format(Locacao.data_inicio, "%y-%m-%d") AS bdate, 
            Veiculo.nome AS nome_veiculo,
            SUM(CASE WHEN SUBSTRING(Tenis.tamanho, 1, 1) = 'M' THEN 1 ELSE 0 END) AS Masculino,
            SUM(CASE WHEN SUBSTRING(Tenis.tamanho, 1, 1) = 'F' THEN 1 ELSE 0 END) AS Feminino,
            SUM(CASE WHEN SUBSTRING(Tenis.tamanho, 1, 1) = 'U' THEN 1 ELSE 0 END) AS Unissex,
            COUNT(1) AS total
        FROM 
            Locacao
        JOIN 
            Veiculo ON Locacao.Veiculo = Veiculo.id
        JOIN 
            Tenis ON Locacao.Tenis = Tenis.id
        GROUP BY 
            date_format(Locacao.data_inicio, "%y-%m-%d"), Veiculo.nome
        ORDER BY 
            date_format(Locacao.data_inicio, "%y-%m-%d") DESC, Veiculo.nome DESC;
        """
    )

    rentals = cur.fetchall()
    fieldnames = [i[0] for i in cur.description]

    if request.method == 'POST':
        now = datetime.now().strftime('%Y-%m-%d')
        filename = f'{now}_estatisticas_gen.xlsx'

        df = pd.DataFrame(rentals, columns=fieldnames)

        # Converter a data para o formato dd/mm/aaaa
        if 'bdate' in df.columns:
            df['bdate'] = pd.to_datetime(df['bdate'], format='%y-%m-%d').dt.strftime('%d/%m/%Y')

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Estatísticas Gen")
        output.seek(0)

        cur.close()
        return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    cur.close()
    return render_template('admin/3-statistics-gen.html', rentals=rentals)


@admin.route('/admin/statistics/num', methods=['GET', 'POST'])
def statistics_num_page():
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT 
            date_format(Locacao.data_inicio, "%y-%m-%d") AS bdate, 
            Veiculo.nome AS nome_veiculo,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 34 THEN 1 ELSE 0 END) AS Tamanho_34,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 35 THEN 1 ELSE 0 END) AS Tamanho_35,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 36 THEN 1 ELSE 0 END) AS Tamanho_36,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 37 THEN 1 ELSE 0 END) AS Tamanho_37,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 38 THEN 1 ELSE 0 END) AS Tamanho_38,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 39 THEN 1 ELSE 0 END) AS Tamanho_39,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 40 THEN 1 ELSE 0 END) AS Tamanho_40,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 41 THEN 1 ELSE 0 END) AS Tamanho_41,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 42 THEN 1 ELSE 0 END) AS Tamanho_42,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 43 THEN 1 ELSE 0 END) AS Tamanho_43,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 44 THEN 1 ELSE 0 END) AS Tamanho_44,
            SUM(CASE WHEN CAST(SUBSTRING(Tenis.tamanho, 2) AS UNSIGNED) = 45 THEN 1 ELSE 0 END) AS Tamanho_45,
            COUNT(1) AS total
        FROM 
            Locacao
        JOIN 
            Veiculo ON Locacao.Veiculo = Veiculo.id
        JOIN 
            Tenis ON Locacao.Tenis = Tenis.id
        GROUP BY 
            date_format(Locacao.data_inicio, "%y-%m-%d"), Veiculo.nome
        ORDER BY 
            date_format(Locacao.data_inicio, "%y-%m-%d") DESC, Veiculo.nome DESC;
        """
    )

    rentals = cur.fetchall()
    fieldnames = [i[0] for i in cur.description]

    if request.method == 'POST':
        now = datetime.now().strftime('%Y-%m-%d')
        filename = f'{now}_estatisticas_num.xlsx'

        df = pd.DataFrame(rentals, columns=fieldnames)

        # Converter a data para o formato dd/mm/aaaa
        if 'bdate' in df.columns:
            df['bdate'] = pd.to_datetime(df['bdate'], format='%y-%m-%d').dt.strftime('%d/%m/%Y')

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Estatísticas Num")
        output.seek(0)

        cur.close()
        return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    cur.close()
    return render_template('admin/3-statistics-num.html', rentals=rentals)


@admin.route('/admin/generatekeys', methods=['GET'])
def generate_keys_page():
    if 'logged_in' in session and session['logged_in']:
        return render_template('admin/4-generate-keys.html')
    else:
        return redirect(url_for('admin.admin_login_page'))


@admin.route('/admin/usersdata', methods=['GET'])
def users_data_page():
    if 'logged_in' in session and session['logged_in']:
        return render_template('admin/5-users-data.html')
    else:
        return redirect(url_for('admin.admin_login_page'))


@admin.route('/admin/logmudancas', methods=['GET'])
def log_mudancas_page():
    if 'logged_in' in session and session['logged_in']:
        return render_template('admin/6-change-log.html')
    else:
        return redirect(url_for('admin.admin_login_page'))


@admin.route('/admin/downloadlogchanges', methods=['GET'])
def download_log_changes():
    cursor = mysql.connection.cursor()
    cursor.execute(
        """ 
        SELECT 
    Promotor.nome AS Promotor, 
    Veiculo.nome AS Veiculo, 
    Modelo.nome AS Modelo,
    Tenis.tamanho AS Tamanho, 
    quantidadeOriginal, 
    quantidadeNova, 
    data 
FROM 
    LogTenis 
JOIN 
    Promotor ON LogTenis.Promotor = Promotor.id 
JOIN 
    Tenis ON LogTenis.Tenis = Tenis.id 
JOIN 
    Veiculo ON LogTenis.Veiculo = Veiculo.id
JOIN 
    Modelo ON Tenis.Modelo = Modelo.id;       
        """)

    # Obter os resultados
    results = cursor.fetchall()

    # Definir os cabeçalhos do CSV
    fieldnames = [i[0] for i in cursor.description]

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d')
    filename = f'{now_str}_log_mudancas.csv'

    # Criar um objeto de resposta CSV
    response = make_response('')
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'

    # Escrever os resultados no arquivo CSV
    writer = csv.DictWriter(response.stream, fieldnames=fieldnames)
    writer.writeheader()
    for row in results:
        writer.writerow(dict(zip(fieldnames, row)))

    return response


@admin.route('/admin/downloadcryptedcsv', methods=['GET'])
def download_users_data_csv():
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT Usuario.id,
           Usuario.dados_criptografados,
           Modelo.nome AS Modelo,
           Tenis.tamanho AS Tamnho,
           Locacao.data_inicio AS Inicio,
           Locacao.data_fim AS Fim,
           Usuario.confirmacao_sms,
           Locacao.status AS Status,
           Promotor.nome AS promotor,
           Locacao.Estande,
           Veiculo.nome AS Veiculo
    FROM Locacao
    JOIN Tenis ON Locacao.Tenis = Tenis.id
    JOIN Modelo ON Tenis.Modelo = Modelo.id
    JOIN Usuario ON Locacao.Usuario = Usuario.id
    JOIN Promotor ON Locacao.Promotor = Promotor.id
    JOIN Veiculo ON Locacao.Veiculo = Veiculo.id
    ORDER BY Locacao.data_inicio DESC;
    """)

    # Obter os resultados
    results = cursor.fetchall()

    # Definir os cabeçalhos do CSV
    fieldnames = [i[0] for i in cursor.description]

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d')
    filename = 'crypted.csv'

    # Criar um objeto de resposta CSV
    response = make_response('')
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'

    writer = csv.DictWriter(response.stream, fieldnames=fieldnames)
    writer.writeheader()
    for row in results:
        writer.writerow(dict(zip(fieldnames, row)))

    return response


@admin.route('/downloadencryptedblob', methods=['POST'])
def download_blob():
    user_id = request.form['user_id']
    cur = mysql.connection.cursor()

    # Executar a consulta SQL para recuperar os dados BLOB
    cur.execute("SELECT documento, retrato FROM Fotos WHERE Usuario = %s", (user_id,))
    data = cur.fetchone()

    if data:
        documento_blob = data[0]
        retrato_blob = data[1]

        # Codificar os bytes em base64
        documento_base64 = base64.b64encode(documento_blob).decode('utf-8')
        retrato_base64 = base64.b64encode(retrato_blob).decode('utf-8')

        response_data = {
            "documento_bytes": documento_base64,
            "retrato_bytes": retrato_base64
        }
        return json.dumps(response_data)
    else:
        return json.dumps({"error": "Dados não encontrados para o usuário fornecido."}), 404

@admin.route('/create_sneaker_model', methods=['POST'])
def create_sneaker_model():
    data = request.json
    modelo_name = data.get("modelo_name")
    estande_name = data.get("estande")

    if not modelo_name or not estande_name:
        return jsonify({"error": "Os campos 'modelo_name' e 'estande' são obrigatórios"}), 400

    try:
        cur = mysql.connection.cursor()

        # Criar o novo modelo na tabela Modelo
        cur.execute("INSERT INTO Modelo (nome, status) VALUES (%s, 'ATIVO')", (modelo_name,))
        mysql.connection.commit()
        modelo_id = cur.lastrowid  # Pega o ID do modelo recém-criado

        # Buscar o ID do Estande pelo nome
        cur.execute("SELECT id FROM Estande WHERE nome = %s", (estande_name,))
        estande_result = cur.fetchone()
        if not estande_result:
            return jsonify({"error": "Estande não encontrado"}), 404
        estande_id = estande_result[0]  # Acessando a primeira posição da tupla corretamente

        # Gerar os tamanhos
        tamanhos = []
        for prefixo in ["F", "M", "U"]:
            for num in range(34, 46):
                tamanhos.append(f"{prefixo}{num}")

        # Inserir os tênis na tabela Tenis
        for tamanho in tamanhos:
            cur.execute("INSERT INTO Tenis (tamanho, quantidade, Estande, Modelo) VALUES (%s, 0, %s, %s)",
                        (tamanho, estande_id, modelo_id))

        mysql.connection.commit()

        return jsonify({"message": "Modelo e Tênis criados com sucesso", "modelo_id": modelo_id, "estande_id": estande_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()


@admin.route('/admin')
def redirect_admin():
    return redirect(url_for('admin.admin_login_page'))


@admin.route('/alive', methods=['GET'])
def is_alive():
    return "YES"
