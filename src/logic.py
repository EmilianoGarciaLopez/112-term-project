from treys import Card, Deck, Evaluator

from constants import *

# * Classes / Logic


class Game:
    def __init__(self):
        self.deck = Deck()
        self.evaluator = Evaluator()

        botPlayers = [
            NaiveBotPlayer(self.deck),
            ConservativeBotPlayer(self.deck),
            TurnerBotPlayer(self.deck),
            FishBotPlayer(self.deck),
            AdvancedBotPlayer(self.deck),
        ]

        random.shuffle(botPlayers)

        self.players = [Player(self.deck)] + botPlayers

        self.communityCards = []
        self.pot = 0
        self.actionTaken = False
        self.hasRaised = False
        self.maxRaise = 0
        self.currentPlayerIndex = 0
        self.consecutiveCalls = 0
        self.sidePots = []  # tuples: (pot size, eligble players)
        self.stage = 0

        self.isFinished = False

        self.smallBlindIndex = 0
        self.bigBlindIndex = 1

        self.postBlinds()
        self.updateAllPlayersPotOdds()

    def postBlinds(self):
        smallBlindPlayer = self.players[self.smallBlindIndex]
        bigBlindPlayer = self.players[self.bigBlindIndex]

        smallBlindPlayer.bet(SMALL_BLIND_AMOUNT, self)
        bigBlindPlayer.bet(BIG_BLIND_AMOUNT, self)

        self.currentPlayerIndex = (self.bigBlindIndex) % NUM_PLAYERS
        print(self.currentPlayerIndex)
        # don't need to adjust current player since that is done elsewhere

        self.nextPlayer()

    def rotateBlinds(self):
        self.smallBlindIndex = (self.smallBlindIndex + 1) % NUM_PLAYERS
        self.bigBlindIndex = (self.bigBlindIndex + 1) % NUM_PLAYERS

    def resetGame(self):
        self.deck = Deck()

        self.communityCards = []
        self.stage = 0

        self.pot = 0
        self.actionTaken = False
        self.hasRaised = False
        self.maxRaise = 0
        self.currentPlayerIndex = 0
        self.consecutiveCalls = 0
        self.sidePots = []
        self.updateAllPlayersPotOdds()

        for player in self.players:
            player.resetForNewRound()
            player.hand = self.deck.draw(NUM_PLAYER_CARDS)
            player.isFolded = False
            player.isAllIn = False

        self.postBlinds()

    def dealFlop(self):
        if self.stage == 0:
            self.communityCards.extend(self.deck.draw(NUM_FLOP_CARDS))
            self.stage = 1
            self.updateAllPlayersPotOdds()

    def dealRiver(self):
        if self.stage == 1 or self.stage == 2:
            self.communityCards.append(self.deck.draw(1)[0])
            self.stage += 1
            self.updateAllPlayersPotOdds()

    def addToPot(self, amount, player=None):  # player parameter is for all-inning
        if player and player.isAllIn:
            self.handleSidePot(amount, player)
        else:
            self.pot += amount

    def advanceStage(self):
        if self.stage == 0:
            self.dealFlop()
        elif self.stage in [1, 2]:
            self.dealRiver()

    def handleSidePot(self, amount, allInPlayer):
        allInAmount = allInPlayer.chipsBetInRound
        remainingAmount = amount

        # adjust side pot and main pots based on all-in amount
        for i, (pot, eligiblePlayers) in enumerate(self.sidePots):
            if allInAmount >= pot:
                allInAmount -= pot
            else:
                extraAmount = pot - allInAmount
                self.sidePots[i] = (allInAmount, eligiblePlayers)
                self.sidePots.append((extraAmount, eligiblePlayers))
                remainingAmount -= allInAmount
                break

        # then main pot is adjusted
        if allInAmount > 0:
            remainingAmount -= allInAmount
            self.sidePots.append(
                (
                    allInAmount,
                    [p for p in self.players if not p.isFolded and p != allInPlayer],
                )
            )

        self.pot += remainingAmount

    def updateRaise(self, totalRoundBet):
        if totalRoundBet > self.maxRaise:
            self.maxRaise = totalRoundBet
            self.hasRaised = True
            print(
                f"Raise updated: maxRaise = {self.maxRaise}, hasRaised = {self.hasRaised}"
            )
        self.hasRaised = True
        self.addToPot(
            totalRoundBet - self.players[self.currentPlayerIndex].chipsBetInRound
        )
        self.consecutiveCalls = 0
        print(
            f"Raise complete: maxRaise = {self.maxRaise}, hasRaised = {self.hasRaised}, consecutiveCalls = {self.consecutiveCalls}"
        )

    def updateAllPlayersPotOdds(self):
        for player in self.players:
            player.calculatePotOdds(self)

    def nextPlayer(self):
        while True:
            activePlayers = [p for p in self.players if not p.isFolded]
            print(f"Active Players: {len(activePlayers)}")  # Debugging
            if len(activePlayers) == 1:
                self.determineWinner()
                break

            self.currentPlayerIndex = (self.currentPlayerIndex + 1) % NUM_PLAYERS
            currentPlayer = self.players[self.currentPlayerIndex]
            print(
                f"Current Player Index: {self.currentPlayerIndex}, Folded: {currentPlayer.isFolded}"
            )  # Debugging

            if (
                isinstance(
                    currentPlayer,
                    (
                        NaiveBotPlayer,
                        ConservativeBotPlayer,
                        TurnerBotPlayer,
                        FishBotPlayer,
                        AdvancedBotPlayer,
                    ),
                )
                and not currentPlayer.isFolded
            ):
                currentPlayer.botAction(self)
                self.actionTaken = True
            elif not currentPlayer.isFolded:
                self.actionTaken = False
                break

            activeNonAllInPlayers = len(
                [p for p in self.players if not p.isFolded and not p.isAllIn]
            )
            print(
                f"Consecutive Calls: {self.consecutiveCalls}, Active Non-All-In Players: {activeNonAllInPlayers}"
            )  # Debugging

            if self.consecutiveCalls >= activeNonAllInPlayers or self.stage == 3:
                if self.stage < 3:
                    self.resetRound()
                    self.advanceStage()
                else:
                    self.determineWinner()

            for player in self.players:
                player.updateCheckOrCall(self)

    def resetRound(self):
        self.actionTaken = False
        self.hasRaised = False
        self.maxRaise = 0
        self.consecutiveCalls = 0
        self.sidePots = []
        self.updateAllPlayersPotOdds()
        for player in self.players:
            player.resetForNewRound()
        print(
            f"Round reset: hasRaised = {self.hasRaised}, maxRaise = {self.maxRaise}, consecutiveCalls = {self.consecutiveCalls}"
        )

    def determineWinner(self):
        # If only one player is left, they win
        activePlayers = [p for p in self.players if not p.isFolded]
        if len(activePlayers) == 1:
            self.awardPot(activePlayers[0])

            self.resetGame()
            self.rotateBlinds()  # Rotate blinds after each round
            return

        if self.stage != 3:  # only runs at end of game
            return

        bestEvalScore = None
        winningPlayer = None
        for player in self.players:
            if player.isFolded:
                continue
            handScore = self.evaluator.evaluate(player.hand, self.communityCards)
            if bestEvalScore is None or handScore < bestEvalScore:
                bestEvalScore = handScore
                winningPlayer = player

        if winningPlayer:
            print(f"Winner detected with {bestEvalScore}")
            self.awardPot(winningPlayer)
            self.resetGame()
            self.rotateBlinds()

    def awardPot(self, winningPlayer):
        winningPlayer.chips += self.pot
        self.pot = 0

        # Award side pots
        for pot, eligiblePlayers in self.sidePots:
            if winningPlayer in eligiblePlayers:
                winningPlayer.chips += pot
            else:
                distAmount = pot / len(eligiblePlayers)
                for player in eligiblePlayers:
                    player.chips += distAmount

        # Reset the side pots
        self.sidePots = []

        if self.players[0].chips == 0:
            self.isFinished = True


import random


class Player:
    def __init__(self, deck):
        self.hand = deck.draw(NUM_PLAYER_CARDS)
        self.isFolded = False
        self.chips = 1000
        self.isAllIn = False
        self.chipsBetInRound = 0
        self.checkOrCall = "Check"

        self.potOdds = float("inf")
        self.winProbability = 0
        self.worthCalling = False

    def calculateWinningProbability(self, game, numSimulations=5_000):
        wins = 0
        knownCards = set(self.hand + game.communityCards)
        numCommunityNeeded = NUM_COMMUNITY_CARDS - len(game.communityCards)

        activePlayersCount = len(
            [
                player
                for player in game.players
                if not player.isFolded and player != self
            ]
        )

        for _ in range(numSimulations):
            simDeck = Deck()
            simDeck.cards = [card for card in simDeck.cards if card not in knownCards]

            # simulate hands for active players
            simHands = [
                simDeck.draw(NUM_PLAYER_CARDS) for _ in range(activePlayersCount)
            ]
            simCommunity = game.communityCards + simDeck.draw(numCommunityNeeded)

            myHandStrength = game.evaluator.evaluate(self.hand, simCommunity)
            if all(
                myHandStrength <= game.evaluator.evaluate(hand, simCommunity)
                for hand in simHands
            ):
                wins += 1

        return wins / numSimulations

    def calculatePotOdds(self, game):
        callAmount = game.maxRaise - self.chipsBetInRound
        winProbability = self.calculateWinningProbability(game) * 100

        if callAmount <= 0:
            self.potOdds = float("inf")
            self.winProbability = winProbability
            self.worthCalling = True
            return

        potOdds = game.pot / callAmount
        worthCalling = winProbability > (1 / (1 + potOdds)) * 100
        self.potOdds = potOdds
        self.winProbability = winProbability
        self.worthCalling = worthCalling

    def evaluateHandStrength(self, communityCards=[]):
        fullHand = self.hand + communityCards

        # to chekc for consecutive values
        sortedHand = sorted(fullHand, key=Card.get_rank_int)

        suitCounts = {}
        rankCounts = {}
        for card in sortedHand:
            suit = Card.get_suit_int(card)
            rank = Card.get_rank_int(card)
            suitCounts[suit] = suitCounts.get(suit, 0) + 1
            rankCounts[rank] = rankCounts.get(rank, 0) + 1

        isFlush = False
        isStraight = False
        flushSuit = None
        for suit, count in suitCounts.items():
            if count >= 5:
                isFlush = True
                flushSuit = suit
                break

        ranks = list(rankCounts.keys())
        ranks.sort()

        # ace can also be 1 for straights
        if 14 in ranks:  # * ace rank = 14
            ranks.append(1)
        for i in range(len(ranks) - 4):
            if ranks[i + 4] - ranks[i] == 4:
                isStraight = True
                break

        if isFlush and isStraight:
            flushCards = [
                card for card in sortedHand if Card.get_suit_int(card) == flushSuit
            ]
            flushRanks = [Card.get_rank_int(card) for card in flushCards]
            flushRanks.sort()
            if flushRanks[-1] == 14 and flushRanks[-5] == 10:
                return "Royal Flush"
            else:
                return "Straight Flush"

        # pairs, three-of-a-kind, and quads
        pairsCount = sum(count == 2 for count in rankCounts.values())
        tripletsCount = sum(count == 3 for count in rankCounts.values())
        quadsCount = sum(count == 4 for count in rankCounts.values())

        if quadsCount:
            return "Quads"
        elif tripletsCount and pairsCount:
            return "Full House"
        elif isFlush:
            return "Flush"
        elif isStraight:
            return "Straight"
        elif tripletsCount:
            return "Triplets"
        elif pairsCount == 2:
            return "Two Pair"
        elif pairsCount:
            return "Pair"
        else:
            return "High Card"

    def canCheck(self, game):
        return game.maxRaise == 0

    def updateCheckOrCall(self, game):
        self.checkOrCall = "Check" if self.canCheck(game) else "Call"

    def allIn(self, game):
        allInAmount = self.chips
        self.chips = 0
        self.isAllIn = True
        game.addToPot(allInAmount, self)
        # https://favtutor.com/blogs/class-name-python
        # TODO: move outside of class or add identifier
        print(f"{self.__class__.__name__} goes All-In with ${allInAmount}")

    def resetForNewRound(self):
        self.chipsBetInRound = 0

    def fold(self):
        self.isFolded = True
        print("Human player folds")

    def bet(self, amount, game):
        totalRoundBet = self.chipsBetInRound + amount
        if amount > self.chips:
            self.allIn(game)
        else:
            self.chips -= amount
            self.chipsBetInRound += amount
            game.addToPot(amount)
            game.updateRaise(totalRoundBet)
            return amount

    def call(self, game):
        callAmount = game.maxRaise - self.chipsBetInRound
        if self.chips >= callAmount:
            self.chips -= callAmount
            game.addToPot(callAmount)
            game.consecutiveCalls += 1
            print(f"Consecutive calls {game.consecutiveCalls}")
            self.chipsBetInRound += callAmount
        else:
            print("Player does not have enough chips and goes all-in")
            self.allIn(game)


class FishBotPlayer(Player):
    def botAction(self, game):
        callAmount = game.maxRaise - self.chipsBetInRound

        if callAmount == 0:
            print("Checks")
            game.consecutiveCalls += 1
            return

        # a fish is basically just a calling machine
        action = random.choices(["raise", "call", "fold"], weights=[1, 4, 1])[0]

        if action == "raise":
            raiseAmount = random.randint(1, self.chips)
            print(f"Raises ${raiseAmount}")
            self.bet(raiseAmount, game)
        elif action == "call":
            print("Calls")
            self.call(game)
        else:
            print("Folds")
            self.fold()

        game.actionTaken = True


class NaiveBotPlayer(Player):
    def botAction(self, game):
        callAmount = game.maxRaise - self.chipsBetInRound

        # checks if it is able to
        if callAmount == 0:
            print("Checks")
            game.consecutiveCalls += 1
            return

        # weighted choice between raising caling and folding, with a weight against raising
        action = random.choices(["raise", "call", "fold"], weights=[1, 3, 2])[0]

        if action == "raise":
            raiseAmount = random.randint(1, self.chips)
            print(f"Raises ${raiseAmount}")
            self.bet(raiseAmount, game)
        elif action == "call":
            print("Calls")
            self.call(game)
        else:
            print("Folds")
            self.fold()

        game.actionTaken = True


"""
This class is named after a friend who notoriously employs this
strategy when playing online poker. It is highly volatile and not 
recommended; usually, it it only effective against other degenerate
gamblers
"""


class TurnerBotPlayer(Player):
    def botAction(self, game):
        self.updateCheckOrCall(game)
        self.calculatePotOdds(game)

        callAmount = game.maxRaise - self.chipsBetInRound

        if game.stage == 0 and callAmount < 40:
            print("Turner calls preflop")
            self.call(game)
        elif self.hasGreatHand():
            print("Turner All-In-s")
            self.allIn(game)
        else:
            print("Turner Folds")
            self.fold()

        game.actionTaken = True

    def hasGreatHand(self):
        handStrength = self.evaluateHandStrength()
        greatHands = ["Quads", "Full House", "Flush", "Straight", "Triplets"]
        return handStrength in greatHands


class ConservativeBotPlayer(Player):
    def botAction(self, game):
        self.updateCheckOrCall(game)
        self.calculatePotOdds(game)

        callAmount = game.maxRaise - self.chipsBetInRound
        potSize = game.pot + callAmount
        winProbability = self.winProbability / 100

        ev = potSize * winProbability - callAmount

        print(
            f"EV: ${ev}, Pot Size: {potSize}, Call Amount: {callAmount}, Win Probability: {winProbability}"
        )

        conservativeCheckThreshold = 15 + 0.05 * potSize
        conservativeCallThreshold = -5
        conservativeRaiseThreshold = 20

        if callAmount == 0:
            if ev < conservativeCheckThreshold:
                print("Checks")
                game.consecutiveCalls += 1
                return

        if ev > conservativeRaiseThreshold:
            if self.chips < callAmount:
                print("All-In due to insufficient chips")
                self.allIn(game)
            else:
                raiseFactor = 1.1  # Only slightly above the minimum raise
                raiseAmount = int(min(callAmount * raiseFactor, self.chips))
                print(f"Raises ${raiseAmount}")
                self.bet(raiseAmount, game)
        elif ev > conservativeCallThreshold:
            print("Calls")
            self.call(game)
        else:
            print("Folds")
            self.fold()

        game.actionTaken = True


class AdvancedBotPlayer(Player):
    def botAction(self, game):
        self.updateCheckOrCall(game)
        self.calculatePotOdds(game)

        # position relative to button
        position = (game.currentPlayerIndex - game.bigBlindIndex) % NUM_PLAYERS

        positionFactor = (
            NUM_PLAYERS - position
        ) / NUM_PLAYERS  # More aggressive in later positions

        callAmount = game.maxRaise - self.chipsBetInRound
        potSize = game.pot + callAmount
        winProbability = self.winProbability / 100

        ev = potSize * winProbability - callAmount
        adjustedEV = ev * positionFactor

        if callAmount == 0:
            if adjustedEV < 10 * positionFactor:
                print("Checks")
                game.consecutiveCalls += 1
                return

        if adjustedEV > 0:
            if self.chips < callAmount:
                print("All-In due to insufficient chips")
                self.allIn(game)
            elif self.chips > 2 * callAmount:
                raiseAmount = int(
                    min(callAmount + random.uniform(1, self.chips / 4), self.chips)
                )
                print(f"Raises ${raiseAmount}")
                self.bet(raiseAmount, game)
            else:
                print("Calls")
                self.call(game)
        elif (
            adjustedEV > -10 * positionFactor
        ):  # Small negative EV, but worth seeing the cards
            print("Calls")
            self.call(game)
        else:
            print("Folds")
            self.fold()

        game.actionTaken = True
