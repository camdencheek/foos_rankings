#!/usr/bin/env python3

from trueskill import Rating, rate
import sqlite3
import datetime
import dateutil.parser
import getch
import sys


class PlayerTable:
  def __init__(self, cursor):
    self.c = cursor

  @staticmethod
  def player_from_row(row):
    return Player(row['name'], row['id'])

  def players(self):
    rows = self.c.execute('''SELECT * FROM players;''').fetchall()
    return [PlayerTable.player_from_row(row) for row in rows]

  def insert_player(self, player):
    self.c.execute('''INSERT INTO players(name) VALUES (?)''', (player.name.lower(),))
    player.id = self.c.lastrowid
    return player

  def get_player(self, player_id):
    self.c.execute('''SELECT * FROM players WHERE id = ?''', (player_id,))
    row = self.c.fetchone()
    if row is None:
      return None
    else:
      return PlayerTable.player_from_row(row)

  def search_name_prefix(self, name):
    rows = self.c.execute('''SELECT * FROM players WHERE name LIKE ?''', (f"{name}%",))
    return [PlayerTable.player_from_row(row) for row in rows]


class Player:
  def __init__(self, name, player_id=None):
    self.id = player_id
    self.name = name

  def __repr__(self):
    return f"({self.id}, {self.name})"

class GameTable:
  def __init__(self, cursor):
    self.c = cursor

  @staticmethod
  def game_from_row(row):
    return Game(
      row['winner1'],
      row['winner2'],
      row['loser1'],
      row['loser2'],
      dateutil.parser.parse(row['date']),
      row['id']
    )

  def games(self):
    rows = self.c.execute('''SELECT winner1, winner2, loser1, loser2, date, id FROM games''').fetchall()
    player_table = PlayerTable(self.c)
    return [ GameTable.game_from_row(row) for row in rows]

  def games_for_player(self, player_id, only_wins=False, only_losses=False):
    assert(not (only_wins and only_losses))
    if only_wins:
      query = f"SELECT winner1, winner2, loser1, loser2, date, id FROM games WHERE winner1 = {player_id} OR winner2 = {player_id}"
    elif only_losses:
      query = f"SELECT winner1, winner2, loser1, loser2, date, id FROM games WHERE loser1 = {player_id} OR loser2 = {player_id}"
    else:
      query = f"SELECT winner1, winner2, loser1, loser2, date, id FROM games WHERE winner1 = {player_id} OR winner2 = {player_id} OR loser1 = {player_id} OR loser2 = {player_id}"

    rows = self.c.execute(query).fetchall()
    return [ GameTable.game_from_row(row) for row in rows]

  def insert_game(self, game):
    self.c.execute('''INSERT INTO games(winner1, winner2, loser1, loser2, date) VALUES (?, ?, ?, ?, ?)''',
                   (game.winners[0], game.winners[1], game.losers[0], game.losers[1], game.date.isoformat()))
    game.id = self.c.lastrowid
    return game

  def get_game(self, game_id):
    rows = self.c.execute('''SELECT * FROM games WHERE id = ? LIMIT 1''', (game_id,))
    return GameTable.game_from_row(row)


class Game:
  def __init__(self, winner1, winner2, loser1, loser2, date=None, game_id=None):
    self.game_id = game_id
    self.winners = (winner1, winner2)
    self.losers = (loser1, loser2)
    self.date = date
    if date is None:
      self.date = datetime.datetime.now()

  def __repr__(self):
    return ",".join(map(str, [self.game_id, self.date, self.winners, self.losers]))

class RatingTable:
  def __init__(self, cursor):
    self.c = cursor

  @staticmethod
  def rating_from_row(row):
    return Rating(
      row['player_id'],
      row['mu'],
      row['sigma'],
      row['id'],
      row['game_id']
    )

  def ratings(self):
    rows = self.c.execute('''SELECT player_id, mu, sigma, id, game_id FROM ratings;''').fetchall()
    return [RatingTable.rating_from_row(row) for row in rows]

  def insert_rating(self, game_id, rating):
    self.c.execute('''INSERT INTO ratings(game_id, player_id, mu, sigma) VALUES (?,?,?,?)''',
                   (game_id, rating.player_id, rating.mu, rating.sigma))
    rating.id = self.c.lastrowid
    return rating

  def player_rating(self, player_id):
    row = self.c.execute('''SELECT player_id, mu, sigma, id, game_id FROM ratings WHERE player_id=? ORDER BY id DESC LIMIT 1''', (player_id,)).fetchone()
    if row is None:
      return Rating(player_id, 500, 200)
    else:
      return RatingTable.rating_from_row(row)

  def create_ratings_from_game(self, game):
    orig1 = self.player_rating(game.winners[0])
    orig2 = self.player_rating(game.winners[1])
    orig3 = self.player_rating(game.losers[0])
    orig4 = self.player_rating(game.losers[1])

    (new1, new2), (new3, new4) = rate([(orig1,orig2),(orig3,orig4)], ranks=[0,1])
    rating1 = Rating(game.winners[0], new1.mu, new1.sigma, game_id=game.id)
    rating2 = Rating(game.winners[1], new2.mu, new2.sigma, game_id=game.id)
    rating3 = Rating(game.losers[0], new3.mu, new3.sigma, game_id=game.id)
    rating4 = Rating(game.losers[1], new4.mu, new4.sigma, game_id=game.id)

    for rating in [rating1, rating2, rating3, rating4]:
      self.insert_rating(game.id, rating)

    return [rating1, rating2, rating3, rating4]

  def latest_ratings(self):
    query = '''
      SELECT *
      FROM ratings
      WHERE ratings.id IN (
        SELECT max(ratings.id)
        FROM ratings
        GROUP BY player_id
      );
    '''
    rows = self.c.execute(query)
    return [RatingTable.rating_from_row(row) for row in rows]



class Rating:
  def __init__(self, player_id, mu, sigma, rating_id=None, game_id=None):
    self.id = rating_id
    self.game_id = game_id
    self.player_id = player_id
    self.mu = mu
    self.sigma = sigma

  def __repr__(self):
    return ','.join(map(str, [self.id, self.game_id, self.player_id, self.mu, self.sigma]))

class Application:
  def __init__(self, database_file):
    conn = sqlite3.connect('rankings.db')
    conn.row_factory = Application.dict_factory
    self.conn = conn
    self.c = self.conn.cursor()
    self.create_tables()

  def __del__(self):
    self.conn.commit()
    self.conn.close()

  @staticmethod
  def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
      d[col[0]] = row[idx]
    return d

  def create_tables(self):
    self.c.execute('''CREATE TABLE IF NOT EXISTS players (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);''')
    self.c.execute('''CREATE TABLE IF NOT EXISTS games (id INTEGER PRIMARY KEY AUTOINCREMENT, winner1 INTEGER, winner2 INTEGER, loser1 INTEGER, loser2 INTEGER, date TEXT);''')
    self.c.execute('''CREATE TABLE IF NOT EXISTS ratings (id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER, player_id INTEGER, mu REAL, sigma REAL);''')

  def request_game_info(self):
    player_table = PlayerTable(self.c)
    rating_table = RatingTable(self.c)

    t1p1 = self.prompt_for_player_name(1,1)
    t1p2 = self.prompt_for_player_name(1,2)
    t2p1 = self.prompt_for_player_name(2,1)
    t2p2 = self.prompt_for_player_name(2,2)

    winner = self.prompt_for_winning_team()
    if winner == 1:
      winner1 = t1p1.id
      winner2 = t1p2.id
      loser1 = t2p1.id
      loser2 = t2p2.id
    else:
      winner1 = t2p1.id
      winner2 = t2p2.id
      loser1 = t1p1.id
      loser2 = t1p2.id

    double = Application.prompt_yes_no("Was this game a double?", default=False)

    return Game(winner1, winner2, loser1, loser2), double

  def process_game(self, game, double=False):
    rating_table = RatingTable(self.c)
    game_table = GameTable(self.c)

    inserted_game = game_table.insert_game(game)
    self.conn.commit()

    ratings = rating_table.create_ratings_from_game(inserted_game)
    self.conn.commit()

    if double:
      inserted_game = game_table.insert_game(game)
      self.conn.commit()

      ratings = rating_table.create_ratings_from_game(inserted_game)
      self.conn.commit()

    return ratings

  def summarize_rankings(self):
    rating_table = RatingTable(self.c)
    player_table = PlayerTable(self.c)
    game_table = GameTable(self.c)

    latest_ratings = rating_table.latest_ratings()
    latest_ratings.sort(key=lambda x: -x.mu)
    print("\n\n==== RATINGS ====")
    for i, rating in enumerate(latest_ratings):
      name = player_table.get_player(rating.player_id).name.title()
      wins = game_table.games_for_player(rating.player_id, only_wins = True)
      losses = game_table.games_for_player(rating.player_id, only_losses = True)
      win_pct = float(len(wins)) / (float(len(wins)) + float(len(losses))) * 100.0
      print(f"{i+1}. {name:20} {rating.mu:0.2f} (±{rating.sigma:0.2f}) {win_pct:0.2f}% Win Rate")

  @staticmethod
  def prompt_yes_no(prompt, default=True):
    chars = {'y': True, 'Y': True, 'N': False, 'n': False, '\n': default}
    while True:
      sys.stdout.write(f"{prompt} [{'Y/n' if default else 'y/N'}] ")
      sys.stdout.flush()
      char = getch.getche()
      result = chars.get(char, None)
      if result is None:
        print("\nPlease respond with 'y' or 'n'")
      else:
        return result

  def prompt_for_player_name(self, team_num, player_num):
    player_table = PlayerTable(self.c)
    while True:
      player_name_prefix = input(f"Team {team_num}, Player {player_num}: ")
      matched_players = player_table.search_name_prefix(player_name_prefix)
      if len(matched_players) == 1:
        return matched_players[0]
      elif len(matched_players) == 0:
        create_player = Application.prompt_yes_no(f"Player {player_name_prefix} does not exist. Create player?")
        if create_player:
          player = player_table.insert_player(Player(player_name_prefix))
          self.conn.commit()
          print(f"Created player {player_name_prefix}")
          return player
        else:
          print(f"You chose not to create player {player_name_prefix}. Exiting.")
          sys.exit(1)
      else:
        matched_player_names = ','.join(map(lambda x: x.name, matched_players))
        print(f"Multiple players ({matched_player_names}) matched the name {player_name_prefix}. Please disambiguate.")
        sys.exit(1)

  def prompt_for_winning_team(self):
    while True:
      sys.stdout.write("Which team won (1 or 2)? ")
      sys.stdout.flush()
      winning_team = getch.getche()
      sys.stdout.write("\n")
      sys.stdout.flush()
      if winning_team == "1":
        return 1
      elif winning_team == "2":
        return 2
      else:
        print("Please enter 1 or 2.")




if __name__ == '__main__':
  app = Application('ratings.db')
  game, double = app.request_game_info()
  app.process_game(game, double)
  app.summarize_rankings()

