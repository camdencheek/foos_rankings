# TrueSkill for Foosball

## Usage

```
$ ./foos.py
Team 1, Player 1: cam
Team 1, Player 2: Josh Williams
Team 2, Player 1: Nathan Gingrich
Player Nathan Gingrich does not exist. Create player? [Y/n]
Created player Nathan Gingrich
Team 2, Player 2: Zack Kendra
Which team won (1 or 2)? 1

==== RATINGS ====
1. Camden Cheek         619.52 (±172.66)
2. Josh Williams        619.52 (±172.66)
3. Nathan Gingrich      452.93 (±186.00)
4. Mary Claire Mikolay  420.06 (±183.39)
5. Zack Kendra          380.48 (±172.66)
```

Just type in the names of the people in the game. After a player has been created (always create players with their full name), the minimum prefix needed to make their name non-ambiguous will do (e.g. 'josh' is enough to get 'Josh Williams' in our office). 

Once you've entered the names of the players, simply select the team that won, and it will print out the latest rankings stored in the database.

## About

This program uses the TrueSkill rating system. TrueSkill is a flexible system which allows for ELO-like rating using a generalized Bayesian inference method that is compatible with individual ratings in multiplayer and team games.

More information about TrueSkill [here](https://www.microsoft.com/en-us/research/wp-content/uploads/2007/01/NIPS2006_0688.pdf).

Players start with a rating of 500 with an uncertianty standard deviation of 200. The uncertainty is reduced the more games are played. Currently, the ranking is based off only the base rating, but in the future to compensate for higher uncertainty of new players, a lower percentile than 50% may be used.

The backend uses a SQLite database that is simply stored in the repo. If easier sharing is required, it should be fairly simple to switch to a Postgres backend.





