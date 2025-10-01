import os
import calendar
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from datetime import date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import io

app = Flask(__name__)

# Configuração do Banco de Dados
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # A linha abaixo é importante para o Render, pois o Heroku (dono do Render) alterou
    # o esquema de postgres para postgresql, mas o SQLAlchemy ainda espera postgresql
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'project.db')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-padrao-para-desenvolvimento')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    telefone = db.Column(db.String(20), nullable=True)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_pedido = db.Column(db.String(50), nullable=False, unique=True)
    cliente_nome = db.Column(db.String(100), nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=False)
    num_parcelas = db.Column(db.Integer)
    data_lancamento = db.Column(db.Date, nullable=False)
    parcelas = db.relationship('Parcela', backref='pedido', lazy=True, cascade="all, delete-orphan")

class Parcela(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    valor = db.Column(db.Float, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pendente')
    parcela_num = db.Column(db.Integer, nullable=False)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user:
            if check_password_hash(user.password, request.form['password']):
                login_user(user)
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('index'))
        flash('Usuário ou senha inválidos. Tente novamente.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- ROTA DE REGISTRO MODIFICADA ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Agora, o registro só é permitido se não houver NENHUM usuário no banco de dados.
    if User.query.count() > 0:
        flash('O registro público está desativado. Apenas o administrador pode criar novos usuários.', 'info')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        # O primeiro usuário criado é sempre um administrador.
        hashed_password = generate_password_hash(request.form['password'], method='scrypt')
        new_user = User(username=request.form['username'], password=hashed_password, is_admin=True)
        db.session.add(new_user)
        db.session.commit()
        flash('Conta de administrador criada com sucesso! Por favor, faça login.', 'success')
        return redirect(url_for('login'))
    
    # Mostra a página de registro apenas se não houver usuários.
    return render_template('register.html')

@app.route('/clientes', methods=['GET', 'POST'])
@login_required
def clientes():
    if request.method == 'POST':
        nome_cliente = request.form['nome']
        telefone_cliente = request.form['telefone']
        novo_cliente = Cliente(nome=nome_cliente, telefone=telefone_cliente)
        db.session.add(novo_cliente)
        db.session.commit()
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    
    todos_clientes = Cliente.query.all()
    return render_template('clientes.html', clientes=todos_clientes)

@app.route('/editar_cliente/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    cliente_a_editar = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente_a_editar.telefone = request.form['telefone']
        db.session.commit()
        flash('Telefone do cliente atualizado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    
    return render_template('editar_cliente.html', cliente=cliente_a_editar)

@app.route('/excluir_cliente/<int:id>')
@login_required
def excluir_cliente(id):
    cliente_a_excluir = Cliente.query.get_or_404(id)
    db.session.delete(cliente_a_excluir)
    db.session.commit()
    return redirect(url_for('clientes'))

@app.route('/pedidos', methods=['GET', 'POST'])
@login_required
def pedidos():
    if request.method == 'POST':
        novo_pedido = Pedido(
            numero_pedido=request.form['numero_pedido'],
            cliente_nome=request.form['cliente_nome'],
            valor_total=float(request.form['valor']),
            forma_pagamento=request.form['forma_pagamento'],
            num_parcelas=int(request.form.get('num_parcelas') or 1),
            data_lancamento=date.today()
        )
        db.session.add(novo_pedido)
        db.session.flush()

        data_vencimento = date.fromisoformat(request.form['data_vencimento'])
        parcela_valor = novo_pedido.valor_total / novo_pedido.num_parcelas
        for i in range(novo_pedido.num_parcelas):
            data_parcela = add_months(data_vencimento, i)
            nova_parcela = Parcela(
                valor=parcela_valor,
                data_vencimento=data_parcela,
                parcela_num=i + 1,
                pedido_id=novo_pedido.id,
                status='Pendente'
            )
            db.session.add(nova_parcela)

        db.session.commit()
        flash('Pedido lançado com sucesso!', 'success')
        return redirect(url_for('pedidos'))

    todos_pedidos = Pedido.query.all()
    return render_template('pedidos.html', pedidos=todos_pedidos)

@app.route('/dar_baixa_parcela/<int:id>', methods=['POST'])
@login_required
def dar_baixa_parcela(id):
    parcela = Parcela.query.get_or_404(id)
    parcela.status = 'Baixado'
    db.session.commit()
    return redirect(request.referrer or url_for('pedidos'))

@app.route('/retirar_baixa_parcela/<int:id>', methods=['POST'])
@login_required
def retirar_baixa_parcela(id):
    parcela = Parcela.query.get_or_404(id)
    parcela.status = 'Pendente'
    db.session.commit()
    return redirect(request.referrer or url_for('pedidos'))

@app.route('/excluir_pedido/<int:id>')
@login_required
def excluir_pedido(id):
    pedido_a_excluir = Pedido.query.get_or_404(id)
    db.session.delete(pedido_a_excluir)
    db.session.commit()
    flash('Pedido excluído com sucesso!', 'success')
    return redirect(url_for('pedidos'))

@app.route('/gestao_financeira', methods=['GET'])
@login_required
def gestao_financeira():
    mes_str = request.args.get('mes')
    ano_str = request.args.get('ano')

    if mes_str and ano_str:
        mes = int(mes_str)
        ano = int(ano_str)
    else:
        hoje = date.today()
        mes = hoje.month
        ano = hoje.year

    parcelas = Parcela.query.order_by(Parcela.data_vencimento).all()
    fluxo_caixa_mensal = {}

    for parcela in parcelas:
        chave_mes = f"{parcela.data_vencimento.year}-{parcela.data_vencimento.month:02d}"
        if chave_mes not in fluxo_caixa_mensal:
            fluxo_caixa_mensal[chave_mes] = {'total_receber': 0, 'total_baixado': 0, 'parcelas': []}
        
        fluxo_caixa_mensal[chave_mes]['parcelas'].append({
            'id': parcela.id,
            'numero_pedido': parcela.pedido.numero_pedido,
            'cliente_nome': parcela.pedido.cliente_nome,
            'valor': parcela.valor,
            'parcelas': f'{parcela.parcela_num}/{parcela.pedido.num_parcelas}',
            'data_vencimento': parcela.data_vencimento,
            'status': parcela.status
        })

        if parcela.status == 'Baixado':
            fluxo_caixa_mensal[chave_mes]['total_baixado'] += parcela.valor
        else:
            fluxo_caixa_mensal[chave_mes]['total_receber'] += parcela.valor

    fluxo_mes_selecionado = fluxo_caixa_mensal.get(f"{ano}-{mes:02d}", {'total_receber': 0, 'total_baixado': 0, 'parcelas': []})
    
    total_a_receber = fluxo_mes_selecionado['total_receber']
    total_baixado = fluxo_mes_selecionado['total_baixado']
    
    parcelas_do_mes = sorted(fluxo_mes_selecionado['parcelas'], key=lambda p: p['data_vencimento'])
    
    meses_disponiveis = sorted(fluxo_caixa_mensal.keys())

    return render_template(
        'gestao_financeira.html',
        parcelas_do_mes=parcelas_do_mes,
        total_a_receber=total_a_receber,
        total_baixado=total_baixado,
        mes=mes,
        ano=ano,
        meses_disponiveis=meses_disponiveis
    )

@app.route('/exportar_pedidos')
@login_required
def exportar_pedidos():
    parcelas = Parcela.query.all()
    
    dados = [{
        'Numero do Pedido': p.pedido.numero_pedido,
        'Cliente': p.pedido.cliente_nome,
        'Valor da Parcela': p.valor,
        'Forma de Pagamento': p.pedido.forma_pagamento,
        'Numero da Parcela': f'{p.parcela_num}/{p.pedido.num_parcelas}',
        'Data de Vencimento': p.data_vencimento,
        'Status': p.status
    } for p in parcelas]

    df = pd.DataFrame(dados)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Parcelas')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='relatorio_financeiro.xlsx'
    )

@app.route('/exportar_clientes')
@login_required
def exportar_clientes():
    clientes = Cliente.query.all()
    
    dados = [{
        'ID': c.id,
        'Nome': c.nome,
        'Telefone': c.telefone if c.telefone else 'N/A',
    } for c in clientes]

    df = pd.DataFrame(dados)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Clientes')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='relatorio_clientes.xlsx'
    )

# --- ROTA ADMIN_USERS MODIFICADA ---
@app.route('/admin_users', methods=['GET'])
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Acesso negado. Você não tem permissão de administrador.', 'error')
        return redirect(url_for('index'))
    todos_usuarios = User.query.all()
    # Passa a contagem de usuários para o template
    user_count = len(todos_usuarios)
    return render_template('admin_users.html', users=todos_usuarios, user_count=user_count)

# --- NOVA ROTA PARA CRIAR USUÁRIOS (SÓ PARA ADMIN) ---
@app.route('/criar_usuario', methods=['POST'])
@login_required
def criar_usuario():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))

    # Verifica o limite de usuários (1 admin + 5 padrão = 6)
    if User.query.count() >= 6:
        flash('Limite de 6 usuários atingido. Não é possível criar novas contas.', 'error')
        return redirect(url_for('admin_users'))

    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        flash('Nome de usuário e senha são obrigatórios.', 'error')
        return redirect(url_for('admin_users'))

    # Verifica se o usuário já existe
    if User.query.filter_by(username=username).first():
        flash(f'O nome de usuário "{username}" já existe.', 'error')
        return redirect(url_for('admin_users'))

    hashed_password = generate_password_hash(password, method='scrypt')
    # Novos usuários criados pelo admin nunca são administradores
    new_user = User(username=username, password=hashed_password, is_admin=False)
    db.session.add(new_user)
    db.session.commit()
    flash(f'Usuário "{username}" criado com sucesso!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/reset_password/<int:user_id>', methods=['POST'])
@login_required
def reset_password(user_id):
    if not current_user.is_admin:
        flash('Acesso negado. Você não tem permissão de administrador.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Você não pode redefinir sua própria senha aqui.', 'error')
        return redirect(url_for('admin_users'))

    nova_senha = request.form['new_password']
    if not nova_senha:
        flash('A nova senha não pode ser vazia.', 'error')
        return redirect(url_for('admin_users'))

    user.password = generate_password_hash(nova_senha, method='scrypt')
    db.session.commit()
    flash(f'A senha do usuário {user.username} foi redefinida com sucesso!', 'success')
    return redirect(url_for('admin_users'))

# --- NOVA ROTA PARA EXCLUIR USUÁRIO (SÓ PARA ADMIN) ---
@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Acesso negado. Você não tem permissão de administrador.', 'error')
        return redirect(url_for('index'))

    user_to_delete = User.query.get_or_404(user_id)

    # Regra de segurança: Não permitir a exclusão de contas de administrador
    if user_to_delete.is_admin:
        flash('Contas de administrador não podem ser excluídas.', 'error')
        return redirect(url_for('admin_users'))

    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'Usuário "{user_to_delete.username}" excluído com sucesso!', 'success')
    return redirect(url_for('admin_users'))

# O bloco a seguir foi removido para preparação para produção.
# O comando 'db.create_all()' será executado pelo build.sh.
# O servidor será iniciado pelo Gunicorn, conforme o Start Command no Render.
#
#    with app.app_context():
#     db.create_all()
#
# if __name__ == '__main__':
#     app.run(debug=True)