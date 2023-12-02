from math import cos, radians, sin

from cmu_graphics import *
from treys import Card, Deck, Evaluator

# * Constants
NUM_PLAYERS = 6
NUM_PLAYER_CARDS = 2
NUM_COMMUNITY_CARDS = 5
NUM_FLOP_CARDS = 3
Y_OFFSET = 100


# * Classes / Logic


class Game:
    def __init__(self):
        self.deck = Deck()
        self.evaluator = Evaluator()
        self.players = [
            Player(self.deck) if i == 0 else BotPlayer(self.deck)
            for i in range(NUM_PLAYERS)
        ]
        self.communityCards = []
        self.pot = 0
        self.actionTaken = False
        self.hasRaised = False
        self.maxRaise = 0
        self.currentPlayerIndex = 0
        self.consecutiveCalls = 0
        self.sidePots = []  # tuples: (pot size, eligble players)
        self.stage = 0

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

    def addToPot(self, amount, player=None):
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
        eligiblePlayers = [p for p in self.players if not p.isFolded and not p.isAllIn]
        self.sidePots.append((amount, eligiblePlayers))

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
        # if only one player remains. TODO: make it so that player doesn't need to accept this by checking — it should just assign the pot
        activePlayers = [p for p in self.players if not p.isFolded]
        if len(activePlayers) == 1:
            self.determineWinner()
            return

        while True:
            self.currentPlayerIndex = (self.currentPlayerIndex + 1) % NUM_PLAYERS
            currentPlayer = self.players[self.currentPlayerIndex]

            if isinstance(currentPlayer, BotPlayer) and not currentPlayer.isFolded:
                currentPlayer.botAction(self)
                self.actionTaken = True
            elif not currentPlayer.isFolded:
                self.actionTaken = False
                break

        # final stage
        if self.consecutiveCalls >= len(activePlayers) or self.stage == 3:
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

    def awardPot(self, winningPlayer):
        winningPlayer.chips += self.pot
        self.pot = 0


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

    def calculateWinningProbability(self, game, numSimulations=1000):
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

    def evaluateHandStrength(self, communityCards):
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


import random  # ! doesn't work if I import random at the top. Suspect conflict with CMU grpahics


class BotPlayer(Player):
    def botAction(self, game):
        self.updateCheckOrCall(game)
        self.calculatePotOdds(game)

        callAmount = game.maxRaise - self.chipsBetInRound
        potSize = game.pot + callAmount
        winProbability = self.winProbability / 100

        # expected value
        ev = potSize * winProbability

        print(
            f"ev: ${ev}, pot size: {potSize}, call amount: {callAmount}, win p {winProbability}"
        )

        randomSmallNumber = random.uniform(1, 25)  # using uniform for floats
        if ev > (callAmount + randomSmallNumber):  # positive EV with some randomness
            additionalEV = ev - callAmount
            raiseMultiplier = random.uniform(1, 1.25)
            raiseAmount = callAmount + additionalEV * raiseMultiplier

            raiseAmount = int(min(raiseAmount, self.chips))

            if raiseAmount > callAmount:
                print(f"raises ${raiseAmount}")
                self.bet(raiseAmount, game)
            else:
                # if the bot can't raise due to chip limit
                self.botCheckOrCall(game)

        elif ev > callAmount:  # if EV justifies calling
            self.botCheckOrCall(game)

        else:
            print("folds")
            self.fold()

        game.actionTaken = True

    def botCheckOrCall(self, game):
        callAmount = game.maxRaise - self.chipsBetInRound
        if callAmount == 0 or self.chips < callAmount:
            print("checks")
            game.consecutiveCalls += 1  #! TODO: unify check method
        else:
            print("calls")
            self.call(game)


# * graphics


def setupGame(app):
    app.backgroundColor = "green"
    app.padding = 20
    app.buttonWidth = 80
    app.buttonHeight = 40
    app.checkButtonLocation = (700, 800)
    app.raiseButtonLocation = (800, 800)
    app.foldButtonLocation = (900, 800)

    app.betAmountStr = ""
    app.raiseButtonLabel = "Bet: $0"

    app.game = Game()
    app.game.updateAllPlayersPotOdds()


def drawTable(app):
    ovalWidth = app.width * 0.8
    ovalHeight = app.height * 0.6
    ovalX = app.width / 2
    ovalY = app.height / 2 - 45 - app.padding / 2
    drawOval(ovalX, ovalY, ovalWidth, ovalHeight, fill="seaGreen")


def drawPlayerArea(app, playerIndex, player):
    angle = (
        360 / NUM_PLAYERS * (playerIndex + 1)
    )  #! + 1 makes the human player appear on the bottom right. DOESN'T MODIFY ACTUAL INDECES
    centerX = app.width / 2
    centerY = app.height / 2 - Y_OFFSET - app.padding
    radiusX = 400
    radiusY = 300

    # https://stackoverflow.com/questions/64176840/finding-radius-of-ellipse-at-angle-a
    # helped me fix my initial method for drawing an oval
    playerX = centerX + radiusX * cos(radians(angle))
    playerY = centerY + radiusY * sin(radians(angle))
    drawCircle(playerX, playerY, 30, fill="black")
    drawLabel(str(player.chips), playerX, playerY, size=14, fill="white")
    drawCards(app, playerX, playerY + 40, player.hand, player.isFolded)

    if not player.isFolded:
        handStrength = player.evaluateHandStrength(app.game.communityCards)

        probLabel = f"{handStrength}, Win: {player.winProbability:.1f}%"

        drawLabel(probLabel, playerX, playerY - 40, size=14, fill="black")


def drawCommunityCards(app):
    startX = app.width / 2
    startY = app.height / 2 - Y_OFFSET - app.padding

    numCardsToDraw = len(app.game.communityCards)
    drawCards(app, startX, startY, app.game.communityCards[:numCardsToDraw])


def drawCards(app, startX, startY, hand, isFolded=False):
    cardWidth = 60
    cardHeight = 90
    cardGap = 15
    cardsCount = len(hand)
    cardsTotalWidth = cardsCount * cardWidth + (cardsCount - 1) * cardGap
    startX -= cardsTotalWidth / 2

    for i, card in enumerate(hand):
        cardStr = Card.int_to_pretty_str(card)[1:-1]

        if cardStr[-1] in [
            "♥",
            "♦",
        ]:
            suitColor = "red"
        else:
            suitColor = "black"

        cardX = startX + i * (cardWidth + cardGap)
        fillColor = "grey" if isFolded else "white"
        drawRect(
            cardX, startY, cardWidth, cardHeight, fill=fillColor, border="darkSlateGray"
        )
        drawLabel(
            cardStr,
            cardX + cardWidth / 2,
            startY + cardHeight / 2,
            size=22,
            fill=suitColor,
        )


def drawButton(app, text, position):
    x, y = position
    drawRect(x, y, app.buttonWidth, app.buttonHeight, fill="lightCoral")
    drawLabel(text, x + app.buttonWidth / 2, y + app.buttonHeight / 2, size=14)


def isWithinButton(app, mouseX, mouseY, buttonPosition):
    x, y = buttonPosition
    return x <= mouseX <= x + app.buttonWidth and y <= mouseY <= y + app.buttonHeight


# * Event Functions


def onMousePress(app, mouseX, mouseY):
    humanPlayer = app.game.players[0]

    if app.game.currentPlayerIndex != 0:
        print("It's not your turn.")
        return

    if humanPlayer.isFolded:
        print("Player has already folded")
        return

    # check/call dependent on hasRaised
    if isWithinButton(app, mouseX, mouseY, app.checkButtonLocation):
        if humanPlayer.checkOrCall == "Call":
            print("Human player calls")
            humanPlayer.call(app.game)
            app.game.actionTaken = True
        else:
            print("Human player checks")
            app.game.actionTaken = True

    if isWithinButton(app, mouseX, mouseY, app.raiseButtonLocation):
        betAmount = int(app.betAmountStr) if app.betAmountStr else 0
        humanPlayer.bet(betAmount, app.game)
        print(f"Human player bets ${betAmount}")
        app.game.actionTaken = True
        resetBetAmount(app)

    elif isWithinButton(app, mouseX, mouseY, app.foldButtonLocation):
        humanPlayer.fold()
        print("Human player folds")
        app.game.actionTaken = True

    # move to next
    if app.game.actionTaken:
        app.game.nextPlayer()


def onKeyPress(app, key):
    if key.isdigit():
        # Add digit to bet amount string and update the bet button label
        app.betAmountStr += key
        updateBetButtonLabel(app)
    elif key == "delete" or key == "backspace":
        # Remove the last digit and update the bet button label
        app.betAmountStr = app.betAmountStr[:-1]
        updateBetButtonLabel(app)


def updateBetButtonLabel(app):
    # Update the bet button label with the current bet amount
    if app.betAmountStr:
        app.raiseButtonLabel = "Bet: $" + app.betAmountStr
    else:
        app.raiseButtonLabel = "Bet: $0"


def resetBetAmount(app):
    # Reset the bet amount string and update the bet button label
    app.betAmountStr = ""
    updateBetButtonLabel(app)


# * App Loop
def onAppStart(app):
    setupGame(app)


def redrawAll(app):
    drawTable(app)
    for i, player in enumerate(app.game.players):
        drawPlayerArea(app, i, player)
    drawCommunityCards(app)
    drawLabel(
        "Pot: $" + str(app.game.pot),
        app.width / 2,
        app.height / 2 + 20,
        size=20,
        fill="white",
    )
    humanPlayer = app.game.players[0]

    drawButton(app, humanPlayer.checkOrCall, app.checkButtonLocation)
    drawButton(app, app.raiseButtonLabel, app.raiseButtonLocation)
    drawButton(app, "Fold", app.foldButtonLocation)


runApp(width=1200, height=1000)
