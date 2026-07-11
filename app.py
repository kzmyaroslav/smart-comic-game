from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
import json
import random
import os
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-it-in-production-12345'
app.config['DEBUG'] = True

# ==============================================
# ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ ДАННЫХ ИГРЫ
# ==============================================
game_state = {
    'players': [],
    'player_status': {},
    'scores': {},
    'current_player_index': 0,
    'current_q_index': 0,
    'game_started': False,
    'questions': [],
    'total_questions': 0,
    'game_created': False,
    'room_id': str(uuid.uuid4())[:8],
    'show_next': False,
    'voting_stage': False,
    'votes': {},
    'voting_completed': False,
    'selected_questions': 0
}


def create_default_questions():
    """Создает файл с вопросами по умолчанию"""
    default_questions = [
        {"question": "Как называется страх перед длинными словами?", "answer": "Гиппопотомонстросескиппедалофобия"},
        {"question": "Какая планета Солнечной системы самая большая?", "answer": "Юпитер"},
        {"question": "Сколько зубов у взрослого человека?", "answer": "32"},
        {"question": "Какое животное самое быстрое на суше?", "answer": "Гепард"},
        {"question": "Сколько океанов на Земле?", "answer": "5"},
        {"question": "Как называется самая высокая гора в мире?", "answer": "Эверест"},
        {"question": "Сколько континентов на Земле?", "answer": "6"},
        {"question": "Как называется столица Франции?", "answer": "Париж"},
        {"question": "Сколько дней в високосном году?", "answer": "366"},
        {"question": "Какая самая большая страна по площади?", "answer": "Россия"},
        {"question": "Сколько лет длилась Столетняя война?", "answer": "116"},
        {"question": "Как звали первого человека в космосе?", "answer": "Юрий Гагарин"},
        {"question": "Сколько цветов в радуге?", "answer": "7"},
        {"question": "Как называется самый большой океан?", "answer": "Тихий океан"},
        {"question": "Сколько костей в теле взрослого человека?", "answer": "206"}
    ]
    
    try:
        with open('questions.json', 'w', encoding='utf-8') as file:
            json.dump(default_questions, file, ensure_ascii=False, indent=4)
        print("✅ Файл questions.json создан")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def load_questions():
    """Загружает вопросы из файла"""
    if not os.path.exists('questions.json'):
        create_default_questions()
        return load_questions()
    
    try:
        with open('questions.json', 'r', encoding='utf-8') as file:
            content = file.read().strip()
            if not content:
                create_default_questions()
                return load_questions()
            questions = json.loads(content)
            if not isinstance(questions, list) or len(questions) == 0:
                create_default_questions()
                return load_questions()
            return questions
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
        create_default_questions()
        return load_questions()


def init_game():
    """Инициализирует глобальное состояние игры"""
    global game_state
    
    if not game_state['game_created']:
        all_questions = load_questions()
        random.shuffle(all_questions)
        
        game_state['questions'] = all_questions[:20]
        game_state['total_questions'] = 0
        game_state['current_q_index'] = 0
        game_state['players'] = []
        game_state['player_status'] = {}
        game_state['scores'] = {}
        game_state['current_player_index'] = 0
        game_state['game_started'] = False
        game_state['game_created'] = True
        game_state['room_id'] = str(uuid.uuid4())[:8]
        game_state['show_next'] = False
        game_state['voting_stage'] = False
        game_state['votes'] = {}
        game_state['voting_completed'] = False
        game_state['selected_questions'] = 0
        print(f"🎮 Создана комната с ID: {game_state['room_id']}")


def get_voting_options(player_count):
    """Возвращает варианты для голосования"""
    options = []
    multiplier = 1
    while True:
        value = player_count * multiplier
        if value > 20:
            break
        options.append(value)
        multiplier += 1
    return options


# ==============================================
# МАРШРУТЫ
# ==============================================

@app.route('/')
def index():
    """Страница входа"""
    init_game()
    
    if 'my_name' in session and session['my_name'] in game_state['players']:
        return redirect(url_for('lobby'))
    
    return render_template('login.html', room_id=game_state['room_id'])


@app.route('/login', methods=['POST'])
def login():
    """Вход игрока"""
    global game_state
    
    player_name = request.form.get('name', '').strip()
    
    if not player_name:
        flash('⚠️ Введите имя!', 'error')
        return redirect(url_for('index'))
    
    if game_state['game_started']:
        flash('❌ Игра уже началась!', 'error')
        return redirect(url_for('index'))
    
    if player_name in game_state['players']:
        flash('⚠️ Игрок уже есть!', 'error')
        return redirect(url_for('index'))
    
    if len(game_state['players']) >= 15:
        flash('❌ Максимум 15 игроков!', 'error')
        return redirect(url_for('index'))
    
    game_state['players'].append(player_name)
    game_state['player_status'][player_name] = False
    game_state['scores'][player_name] = 0
    game_state['votes'][player_name] = None
    
    session['my_name'] = player_name
    
    flash(f'✅ Добро пожаловать, {player_name}!', 'success')
    return redirect(url_for('lobby'))


@app.route('/lobby')
def lobby():
    """Комната ожидания"""
    global game_state
    
    my_name = session.get('my_name')
    if not my_name or my_name not in game_state['players']:
        flash('❌ Войдите в игру', 'error')
        return redirect(url_for('index'))
    
    if game_state['game_started']:
        return redirect(url_for('game'))
    
    all_ready = all(game_state['player_status'].get(player, False) for player in game_state['players']) and len(game_state['players']) >= 2
    
    if all_ready and not game_state['voting_stage']:
        game_state['voting_stage'] = True
        game_state['voting_completed'] = False
        game_state['votes'] = {player: None for player in game_state['players']}
        flash('🗳️ Голосование!', 'info')
        return redirect(url_for('voting'))
    
    return render_template('lobby.html',
                         my_name=my_name,
                         players=game_state['players'],
                         player_status=game_state['player_status'])


@app.route('/toggle_ready', methods=['POST'])
def toggle_ready():
    """Переключает статус готовности"""
    global game_state
    
    print("🔵 /toggle_ready вызван")
    
    my_name = session.get('my_name')
    if not my_name or my_name not in game_state['players']:
        print("❌ Игрок не авторизован")
        return jsonify({'error': 'Not logged in'}), 401
    
    if game_state['game_started']:
        print("❌ Игра уже началась")
        return jsonify({'error': 'Game already started'}), 400
    
    current_status = game_state['player_status'].get(my_name, False)
    game_state['player_status'][my_name] = not current_status
    
    all_ready = all(game_state['player_status'].get(player, False) for player in game_state['players']) and len(game_state['players']) >= 2
    
    print(f"🔄 {my_name} {'готов' if game_state['player_status'][my_name] else 'не готов'}")
    print(f"📊 Все готовы: {all_ready}")
    
    return jsonify({
        'status': game_state['player_status'][my_name],
        'all_ready': all_ready,
        'player_count': len(game_state['players'])
    })


@app.route('/lobby_status')
def lobby_status():
    """Статус комнаты"""
    global game_state
    
    my_name = session.get('my_name')
    if not my_name:
        return jsonify({'error': 'Not logged in'}), 401
    
    return jsonify({
        'players': game_state['players'],
        'player_status': game_state['player_status'],
        'game_started': game_state['game_started'],
        'my_name': my_name,
        'room_id': game_state['room_id'],
        'scores': game_state['scores'],
        'current_q_index': game_state['current_q_index'],
        'current_player_index': game_state['current_player_index'],
        'show_next': game_state.get('show_next', False),
        'total_questions': game_state['total_questions'],
        'voting_stage': game_state.get('voting_stage', False)  # <-- ЭТО ВАЖНО!
    })


@app.route('/voting')
def voting():
    """Страница голосования"""
    global game_state
    
    my_name = session.get('my_name')
    if not my_name or my_name not in game_state['players']:
        return redirect(url_for('index'))
    
    if game_state['voting_completed']:
        return redirect(url_for('game'))
    
    if game_state['game_started']:
        return redirect(url_for('game'))
    
    player_count = len(game_state['players'])
    options = get_voting_options(player_count)
    votes = game_state['votes']
    
    all_voted = all(vote is not None for vote in votes.values())
    
    if all_voted and not game_state['voting_completed']:
        vote_counts = {}
        for option in options:
            vote_counts[option] = list(votes.values()).count(option)
        
        max_votes = max(vote_counts.values())
        winning_options = [option for option, count in vote_counts.items() if count == max_votes]
        
        if len(winning_options) > 1:
            selected = random.choice(winning_options)
        else:
            selected = winning_options[0]
        
        game_state['selected_questions'] = selected
        game_state['voting_completed'] = True
        
        all_questions = game_state['questions']
        game_state['questions'] = all_questions[:selected]
        game_state['total_questions'] = selected
        game_state['current_q_index'] = 0
        
        flash(f'🎮 Выбрано {selected} вопросов!', 'success')
        return redirect(url_for('game'))
    
    return render_template('voting.html',
                         my_name=my_name,
                         players=game_state['players'],
                         options=options,
                         votes=votes,
                         voting_completed=game_state['voting_completed'],
                         selected_questions=game_state['selected_questions'])


@app.route('/vote', methods=['POST'])
def vote():
    """Обрабатывает голос"""
    global game_state
    
    my_name = session.get('my_name')
    if not my_name or my_name not in game_state['players']:
        return jsonify({'error': 'Not logged in'}), 401
    
    if game_state['voting_completed']:
        return jsonify({'error': 'Voting completed'}), 400
    
    option = request.form.get('option')
    if not option:
        return jsonify({'error': 'No option'}), 400
    
    option = int(option)
    player_count = len(game_state['players'])
    valid_options = get_voting_options(player_count)
    
    if option not in valid_options:
        return jsonify({'error': 'Invalid option'}), 400
    
    game_state['votes'][my_name] = option
    
    return jsonify({'success': True, 'voted': True})


@app.route('/voting_status')
def voting_status():
    """Статус голосования"""
    global game_state
    
    my_name = session.get('my_name')
    if not my_name:
        return jsonify({'error': 'Not logged in'}), 401
    
    return jsonify({
        'votes': game_state['votes'],
        'all_voted': all(vote is not None for vote in game_state['votes'].values()),
        'voting_completed': game_state['voting_completed'],
        'selected_questions': game_state['selected_questions']
    })


@app.route('/game')
def game():
    """Игровая страница"""
    global game_state
    
    my_name = session.get('my_name')
    if not my_name or my_name not in game_state['players']:
        return redirect(url_for('index'))
    
    if not game_state['game_started'] and game_state['voting_completed']:
        game_state['game_started'] = True
        game_state['current_player_index'] = random.randint(0, len(game_state['players']) - 1)
        game_state['current_q_index'] = 0
        game_state['show_next'] = False
    
    if not game_state['voting_completed']:
        return redirect(url_for('voting'))
    
    if not game_state['game_started']:
        return redirect(url_for('lobby'))
    
    players = game_state['players']
    scores = game_state['scores']
    q_index = game_state['current_q_index']
    questions = game_state['questions']
    total_questions = game_state['total_questions']
    
    if q_index >= len(questions) or q_index >= total_questions:
        return redirect(url_for('results'))
    
    player_index = game_state['current_player_index']
    current_host = players[player_index % len(players)] if players else None
    
    is_host = (my_name == current_host)
    
    question_data = questions[q_index] if q_index < len(questions) else None
    
    next_player_index = (player_index + 1) % len(players) if players else 0
    next_host = players[next_player_index] if players else None
    
    return render_template('game.html',
                         my_name=my_name,
                         players=players,
                         scores=scores,
                         question=question_data['question'] if question_data else None,
                         answer=question_data['answer'] if question_data and is_host else None,
                         is_host=is_host,
                         host=current_host,
                         next_host=next_host,
                         q_num=q_index + 1,
                         total=total_questions,
                         show_next=game_state.get('show_next', False))


@app.route('/action', methods=['POST'])
def action():
    """Действия ведущего"""
    global game_state
    
    my_name = session.get('my_name')
    if not my_name or my_name not in game_state['players']:
        return redirect(url_for('index'))
    
    players = game_state['players']
    q_index = game_state['current_q_index']
    player_index = game_state['current_player_index']
    current_host = players[player_index % len(players)] if players else None
    
    if my_name != current_host:
        flash('❌ Только ведущий!', 'error')
        return redirect(url_for('game'))
    
    action_type = request.form.get('action')
    target_player = request.form.get('player')
    scores = game_state['scores']
    
    if target_player == current_host:
        flash('❌ Нельзя себе!', 'error')
        return redirect(url_for('game'))
    
    if action_type == 'correct':
        if target_player and target_player in scores:
            scores[target_player] = scores.get(target_player, 0) + 2
            game_state['show_next'] = True
            flash(f'✅ +2 балла {target_player}!', 'success')
            return redirect(url_for('game'))
    
    elif action_type == 'partial':
        if target_player and target_player in scores:
            scores[target_player] = scores.get(target_player, 0) + 1
            flash(f'➕ +1 балл {target_player}!', 'success')
            return redirect(url_for('game'))
    
    elif action_type == 'wrong':
        if target_player and target_player in scores:
            scores[target_player] = scores.get(target_player, 0) - 1
            flash(f'➖ -1 балл {target_player}!', 'info')
            return redirect(url_for('game'))
    
    elif action_type == 'next':
        game_state['current_q_index'] = q_index + 1
        game_state['current_player_index'] = (player_index + 1) % len(players)
        game_state['show_next'] = False
        flash('➡️ Следующий вопрос!', 'info')
        return redirect(url_for('game'))
    
    elif action_type == 'skip':
        game_state['current_q_index'] = q_index + 1
        game_state['current_player_index'] = (player_index + 1) % len(players)
        game_state['show_next'] = False
        flash('⏭️ Вопрос пропущен!', 'info')
        return redirect(url_for('game'))
    
    return redirect(url_for('game'))


@app.route('/results')
def results():
    """Результаты"""
    global game_state
    
    scores = game_state['scores']
    sorted_players = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    winner = sorted_players[0][0] if sorted_players else None
    
    return render_template('results.html',
                         sorted_players=sorted_players,
                         winner=winner,
                         room_id=game_state['room_id'],
                         total_questions=game_state['total_questions'])


@app.route('/reset')
def reset():
    """Сброс игры"""
    global game_state
    
    game_state = {
        'players': [],
        'player_status': {},
        'scores': {},
        'current_player_index': 0,
        'current_q_index': 0,
        'game_started': False,
        'questions': [],
        'total_questions': 0,
        'game_created': False,
        'room_id': str(uuid.uuid4())[:8],
        'show_next': False,
        'voting_stage': False,
        'votes': {},
        'voting_completed': False,
        'selected_questions': 0
    }
    
    session.clear()
    flash('🔄 Новая комната!', 'info')
    return redirect(url_for('index'))


@app.route('/room_info')
def room_info():
    """Информация о комнате"""
    global game_state
    
    return jsonify({
        'room_id': game_state['room_id'],
        'players': game_state['players'],
        'player_count': len(game_state['players']),
        'game_started': game_state['game_started']
    })


if __name__ == '__main__':
    init_game()
    print("=" * 50)
    print("🚀 Запуск игры 'Самый умный ПЕПЕ'...")
    print(f"🏠 ID комнаты: {game_state['room_id']}")
    print("📝 Проверяю файл questions.json...")
    load_questions()
    print("✅ Все готово!")
    print("🌐 Откройте http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)