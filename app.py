# CÓDIGO ATUALIZADO E COMPLETO
# Este arquivo substitui o método de criptografia para garantir a compatibilidade.

import os
import calendar
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import io

# Inicialização da Aplicação Flask
app = Flask(__name__)

# --- Configuração do Banco de Dados ---
# Detecta se está rodando no Render (com DATABASE_URL) ou localmente.
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Corrige o prefixo da URL do banco de dados para o padrão do SQLAlchemy
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Configuração para banco de dados local (SQLite)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'project.db')

# --- Configurações Gerais da Aplicação ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-forte-para-desenvolvimento-local')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Inicialização de Extensões ---
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Modelos do Banco de Dados (Estrutura das Tabelas) ---

@login_manager.user_loader
def load_user(user_id):
    """Carrega o usuário atual da sessão."""
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    """Modelo para a tabela de usuários."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Cliente(db.Model):
    """Modelo para a tabela de clientes."""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    telefone = db.Column(db.String(20), nullable=True)

class Pedido(db.Model):
    """Modelo para a tabela de pedidos."""
    id = db.Column(db.Integer, primary_key=True)
    numero_pedido = db.Column(db.String(50), nullable=False, unique=True)
    cliente_nome = db.Column(db.String(100), nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=False)
    num_parcelas = db.Column(db.Integer)
    data_lancamento = db.Column(db.Date, nullable=False)
    parcelas = db.relationship('Parcela', backref='pedido', lazy=True, cascade="all, delete-orphan")

class Parcela(db.Model):
    """Modelo para a tabela de parcelas."""
    id = db.Column(db.Integer, primary_key=True)
    valor = db.Column(db.Float, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pendente')
    parcela_num = db.Column(db.Integer, nullable=False)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)

# --- Funções e Contexto ---

@app.context_processor
def inject_user():
    """Injeta a variável 'current_user' em todos os templates."""
    return dict(current_user=current_user)

def add_months(sourcedate, months):
    """Adiciona meses a uma data, corrigindo para o último dia do mês se necessário."""
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

# --- Rotas da Aplicação ---

@app.route('/')
def index():
    """Página inicial."""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos. Tente novamente.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Rota para fazer logout."""
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Página de registro, acessível apenas se não houver usuários no sistema."""
    if User.query.count() > 0:
        flash('O registro público está desativado. Apenas o administrador pode criar novos usuários.', 'info')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        hashed_password = generate_password_hash(request.form['password'])
        new_user = User(username=request.form['username'], password=hashed_password, is_admin=True)
        db.session.add(new_user)
        db.session.commit()
        flash('Conta de administrador criada com sucesso! Por favor, faça login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/clientes', methods=['GET', 'POST'])
@login_required
def clientes():
    """Página para gerenciar clientes."""
    if request.method == 'POST':
        novo_cliente = Cliente(nome=request.form['nome'], telefone=request.form['telefone'])
        db.session.add(novo_cliente)
        db.session.commit()
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    
    todos_clientes = Cliente.query.all()
    return render_template('clientes.html', clientes=todos_clientes)

@app.route('/editar_cliente/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    """Página para editar um cliente existente."""
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.telefone = request.form['telefone']
        db.session.commit()
        flash('Telefone do cliente atualizado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    
    return render_template('editar_cliente.html', cliente=cliente)

@app.route('/excluir_cliente/<int:id>')
@login_required
def excluir_cliente(id):
    """Rota para excluir um cliente."""
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente excluído com sucesso!', 'success')
    return redirect(url_for('clientes'))

@app.route('/pedidos', methods=['GET', 'POST'])
@login_required
def pedidos():
    """Página para gerenciar pedidos."""
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

        data_vencimento_primeira = date.fromisoformat(request.form['data_vencimento'])
        valor_parcela = novo_pedido.valor_total / novo_pedido.num_parcelas
        for i in range(novo_pedido.num_parcelas):
            data_parcela = add_months(data_vencimento_primeira, i)
            nova_parcela = Parcela(valor=valor_parcela, data_vencimento=data_parcela, parcela_num=i + 1, pedido_id=novo_pedido.id)
            db.session.add(nova_parcela)

        db.session.commit()
        flash('Pedido lançado com sucesso!', 'success')
        return redirect(url_for('pedidos'))

    todos_pedidos = Pedido.query.all()
    return render_template('pedidos.html', pedidos=todos_pedidos)

@app.route('/dar_baixa_parcela/<int:id>', methods=['POST'])
@login_required
def dar_baixa_parcela(id):
    """Muda o status de uma parcela para 'Baixado'."""
    parcela = Parcela.query.get_or_404(id)
    parcela.status = 'Baixado'
    db.session.commit()
    return redirect(request.referrer or url_for('pedidos'))

@app.route('/retirar_baixa_parcela/<int:id>', methods=['POST'])
@login_required
def retirar_baixa_parcela(id):
    """Retorna o status de uma parcela para 'Pendente'."""
    parcela = Parcela.query.get_or_404(id)
    parcela.status = 'Pendente'
    db.session.commit()
    return redirect(request.referrer or url_for('pedidos'))

@app.route('/excluir_pedido/<int:id>')
@login_required
def excluir_pedido(id):
    """Exclui um pedido e suas parcelas associadas."""
    pedido = Pedido.query.get_or_404(id)
    db.session.delete(pedido)
    db.session.commit()
    flash('Pedido excluído com sucesso!', 'success')
    return redirect(url_for('pedidos'))

@app.route('/gestao_financeira')
@login_required
def gestao_financeira():
    """Página de visualização do fluxo de caixa."""
    hoje = date.today()
    mes = int(request.args.get('mes', hoje.month))
    ano = int(request.args.get('ano', hoje.year))

    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])

    parcelas_do_mes = Parcela.query.filter(Parcela.data_vencimento.between(primeiro_dia, ultimo_dia)).order_by(Parcela.data_vencimento).all()
    
    # AJUSTE: Formata os dados para a exibição correta no template
    dados_formatados = []
    for p in parcelas_do_mes:
        dados_formatados.append({
            'numero_pedido': p.pedido.numero_pedido,
            'cliente_nome': p.pedido.cliente_nome,
            'valor': p.valor,
            'parcelas': f'{p.parcela_num}/{p.pedido.num_parcelas}',
            'data_vencimento': p.data_vencimento,
            'status': p.status
        })
    
    total_a_receber = sum(p['valor'] for p in dados_formatados if p['status'] == 'Pendente')
    total_baixado = sum(p['valor'] for p in dados_formatados if p['status'] == 'Baixado')

    return render_template(
        'gestao_financeira.html',
        parcelas_do_mes=dados_formatados,
        total_a_receber=total_a_receber,
        total_baixado=total_baixado,
        mes=mes,
        ano=ano
    )

@app.route('/exportar_pedidos')
@login_required
def exportar_pedidos():
    """Exporta todas as parcelas para um arquivo Excel."""
    parcelas = Parcela.query.order_by(Parcela.data_vencimento).all()
    dados = [{
        'Numero do Pedido': p.pedido.numero_pedido, 'Cliente': p.pedido.cliente_nome,
        'Valor da Parcela': p.valor, 'Forma de Pagamento': p.pedido.forma_pagamento,
        'Numero da Parcela': f'{p.parcela_num}/{p.pedido.num_parcelas}',
        'Data de Vencimento': p.data_vencimento, 'Status': p.status
    } for p in parcelas]
    df = pd.DataFrame(dados)
    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name='Parcelas')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='relatorio_financeiro.xlsx')

@app.route('/exportar_clientes')
@login_required
def exportar_clientes():
    """Exporta todos os clientes para um arquivo Excel."""
    clientes = Cliente.query.all()
    dados = [{'ID': c.id, 'Nome': c.nome, 'Telefone': c.telefone if c.telefone else 'N/A'} for c in clientes]
    df = pd.DataFrame(dados)
    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name='Clientes')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='relatorio_clientes.xlsx')

@app.route('/admin_users')
@login_required
def admin_users():
    """Painel de administração de usuários."""
    if not current_user.is_admin:
        flash('Acesso negado. Você não tem permissão de administrador.', 'error')
        return redirect(url_for('index'))
    todos_usuarios = User.query.all()
    user_count = len(todos_usuarios)
    return render_template('admin_users.html', users=todos_usuarios, user_count=user_count)

@app.route('/criar_usuario', methods=['POST'])
@login_required
def criar_usuario():
    """Rota para o admin criar novos usuários."""
    if not current_user.is_admin:
        return redirect(url_for('index'))
    if User.query.count() >= 6:
        flash('Limite de 6 usuários atingido.', 'error')
        return redirect(url_for('admin_users'))
    username = request.form.get('username')
    password = request.form.get('password')
    if User.query.filter_by(username=username).first():
        flash(f'O nome de usuário "{username}" já existe.', 'error')
        return redirect(url_for('admin_users'))
    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password, is_admin=False)
    db.session.add(new_user)
    db.session.commit()
    flash(f'Usuário "{username}" criado com sucesso!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/reset_password/<int:user_id>', methods=['POST'])
@login_required
def reset_password(user_id):
    """Rota para o admin redefinir a senha de um usuário."""
    if not current_user.is_admin:
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    nova_senha = request.form['new_password']
    user.password = generate_password_hash(nova_senha)
    db.session.commit()
    flash(f'A senha do usuário {user.username} foi redefinida com sucesso!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Rota para o admin excluir um usuário."""
    if not current_user.is_admin:
        return redirect(url_for('index'))
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.is_admin:
        flash('Contas de administrador não podem ser excluídas.', 'error')
        return redirect(url_for('admin_users'))
    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'Usuário "{user_to_delete.username}" excluído com sucesso!', 'success')
    return redirect(url_for('admin_users'))

# Bloco para execução direta e criação do banco de dados
#if __name__ == '__main__':
#    with app.app_context():
        # Cria todas as tabelas no banco de dados se elas ainda não existirem
#        db.create_all()
    # Inicia o servidor de desenvolvimento
#    app.run(debug=True)
