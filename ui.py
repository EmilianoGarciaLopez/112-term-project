from math import cos, radians, sin
from random import choice

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

    def dealFlop(self):
        if self.stage == 0:
            self.communityCards.extend(self.deck.draw(NUM_FLOP_CARDS))
            self.stage = 1

    def dealRiver(self):
        if self.stage == 1 or self.stage == 2:
            self.communityCards.append(self.deck.draw(1)[0])
            self.stage += 1

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
        self.addToPot(
            totalRoundBet - self.players[self.currentPlayerIndex].chipsBetInRound
        )  #! TEST: make sure this accounts for amount already bet
        self.consecutiveCalls = 0

    def nextPlayer(self):
        # continue until human player
        while True:
            self.currentPlayerIndex = (self.currentPlayerIndex + 1) % NUM_PLAYERS
            currentPlayer = self.players[self.currentPlayerIndex]

            if isinstance(currentPlayer, BotPlayer) and not currentPlayer.isFolded:
                currentPlayer.botAction(self)
            else:
                # if round is complete
                activePlayers = [p for p in self.players if not p.isFolded]
                if self.consecutiveCalls >= len(activePlayers) - 1:
                    self.resetRound()  # Resetting the round TODO: implement multi-round functionality
                    self.advanceStage()
                    break

                # check if game should end
                if self.stage == 3 or all(
                    p.isFolded
                    for p in self.players
                    if p != self.players[self.currentPlayerIndex]
                ):
                    self.determineWinner()
                    break

    def resetRound(self):
        self.actionTaken = False
        self.hasRaised = False
        self.maxRaise = 0
        self.consecutiveCalls = 0
        self.sidePots = []
        for player in self.players:
            player.resetForNewRound()  # TODO: refactor

    def determineWinner(self):
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
            game.updateRaise(totalRoundBet)
            return amount

    def call(self, game):
        callAmount = game.maxRaise
        if self.chips >= callAmount:
            self.chips -= callAmount
            game.addToPot(callAmount)
            game.consecutiveCalls += 1
            print(f"Player calls ${callAmount}")
        else:
            print("Player does not have enough chips and goes all-in")
            self.allIn(game)


class BotPlayer(Player):
    def botAction(self, game):
        if game.hasRaised:
            action = choice(["call", "call", "call"])
        else:
            action = choice(["check", "check", "check", "raise"])

        botIdentifier = f"Bot {game.players.index(self) + 1}"

        if action == "check":
            print(f"{botIdentifier} checks")
            game.actionTaken = True
        elif action == "call":
            self.call(game)
            print(f"{botIdentifier} calls ${game.maxRaise}")
        elif action == "raise":
            raiseAmount = game.maxRaise + 20 if game.hasRaised else 20
            self.bet(raiseAmount, game)
            print(f"{botIdentifier} raises ${raiseAmount}")


# * graphics


def setupGame(app):
    app.backgroundColor = "green"
    app.padding = 20
    app.buttonWidth = 80
    app.buttonHeight = 40
    app.checkButtonLocation = (700, 800)
    app.raiseButtonLocation = (800, 800)
    app.foldButtonLocation = (900, 800)

    app.game = Game()


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


def drawCommunityCards(app):
    startX = app.width / 2
    startY = app.height / 2 - Y_OFFSET - app.padding

    # Only draw the number of cards based on the current stage
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
        if app.game.hasRaised:
            print("Human player calls")
            humanPlayer.call(app.game)
        else:
            print("Human player checks")
            app.game.actionTaken = True

    elif isWithinButton(app, mouseX, mouseY, app.raiseButtonLocation):
        betAmount = app.game.maxRaise + 20
        humanPlayer.bet(betAmount, app.game)
        print(f"Human player raises ${betAmount}")
        app.game.actionTaken = True

    elif isWithinButton(app, mouseX, mouseY, app.foldButtonLocation):
        humanPlayer.fold()
        print("Human player folds")
        app.game.actionTaken = True

    # move to next
    if app.game.actionTaken:
        app.game.nextPlayer()


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
    checkStr = "Check" if app.game.maxRaise == 0 else "Call"
    drawButton(app, checkStr, app.checkButtonLocation)
    drawButton(app, "Raise", app.raiseButtonLocation)
    drawButton(app, "Fold", app.foldButtonLocation)


runApp(width=1200, height=1000)
