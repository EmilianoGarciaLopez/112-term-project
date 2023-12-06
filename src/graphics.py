import os
import pathlib

from cmu_graphics import *
from PIL import Image
from treys import Card

from constants import *
from logic import Game


def setupGame(app):
    app.padding = 20
    app.buttonWidth = 80
    app.buttonHeight = 40
    app.checkButtonLocation = (660, 820)
    app.raiseButtonLocation = (760, 820)
    app.foldButtonLocation = (860, 820)

    app.showOtherPlayersCards = False
    app.toggleButtonLocation = (760, 880)

    app.betAmountStr = ""

    app.image = Image.open("background.jpg")
    app.image = app.image.resize((1200, 1000))
    app.image = CMUImage(app.image)

    app.game = Game()


def drawTable(app):
    drawImage(
        app.image,
        app.width / 2,
        app.height / 2,
        align="center",
    )

    # Now we're using images, so this isn't necessary

    # ovalWidth = app.width * 0.8
    # ovalHeight = app.height * 0.6
    # ovalX = app.width / 2
    # ovalY = app.height / 2 - 45 - app.padding / 2
    # drawOval(ovalX, ovalY, ovalWidth + 20, ovalHeight + 20, fill=rgb(124, 86, 70))
    # drawOval(ovalX, ovalY, ovalWidth, ovalHeight, fill="seaGreen")


def drawPlayerArea(app, playerIndex, player):
    angle = 360 / NUM_PLAYERS * (playerIndex + 1)
    centerX = app.width / 2
    centerY = app.height / 2 - Y_OFFSET - app.padding
    radiusX = 400
    radiusY = 300

    playerX = centerX + radiusX * cos(radians(angle))
    playerY = centerY + radiusY * sin(radians(angle))
    drawCircle(playerX, playerY, 30, fill="black")
    drawLabel(str(player.chips), playerX, playerY, size=14, fill="white")

    playerClassName = type(player).__name__
    drawLabel(playerClassName, playerX, playerY - 60, size=14, fill="white")

    if playerIndex == 0 or app.showOtherPlayersCards:
        drawCards(app, playerX, playerY + 40, player.hand, player.isFolded)
        handStrength = player.evaluateHandStrength(app.game.communityCards)
        probLabel = f"{handStrength}, Win: {player.winProbability:.1f}%"
        drawLabel(probLabel, playerX, playerY - 40, size=14, fill="white")
    else:
        drawFacedownCards(app, playerX, playerY + 40, len(player.hand), player.isFolded)


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
        drawRect(cardX, startY, cardWidth, cardHeight, fill=fillColor)
        drawLabel(
            cardStr,
            cardX + cardWidth / 2,
            startY + cardHeight / 2,
            size=22,
            fill=suitColor,
        )


def drawFacedownCards(app, startX, startY, numCards, isFolded=False):
    cardWidth = 60
    cardHeight = 90
    cardGap = 15
    cardsTotalWidth = numCards * cardWidth + (numCards - 1) * cardGap
    startX -= cardsTotalWidth / 2

    fillColor = "grey" if isFolded else "darkRed"

    for i in range(numCards):
        cardX = startX + i * (cardWidth + cardGap)
        drawRect(cardX, startY, cardWidth, cardHeight, fill=fillColor)


def drawButton(app, text, position):
    x, y = position
    drawRect(x, y, app.buttonWidth, app.buttonHeight, fill="silver")
    drawLabel(
        text, x + app.buttonWidth / 2, y + app.buttonHeight / 2, size=14, fill="black"
    )


def isWithinButton(app, mouseX, mouseY, buttonPosition):
    x, y = buttonPosition
    return x <= mouseX <= x + app.buttonWidth and y <= mouseY <= y + app.buttonHeight


# * Event Functions


def game_onMousePress(app, mouseX, mouseY):
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
        app.betAmountStr = ""

    elif isWithinButton(app, mouseX, mouseY, app.foldButtonLocation):
        humanPlayer.fold()
        print("Human player folds")
        app.game.actionTaken = True

    if isWithinButton(app, mouseX, mouseY, app.toggleButtonLocation):
        app.showOtherPlayersCards = not (app.showOtherPlayersCards)

    # move to next
    if app.game.actionTaken:
        app.game.nextPlayer()


def game_onKeyPress(app, key):
    if key.isdigit():
        app.betAmountStr += key

    elif key == "delete" or key == "backspace":
        # remove the last digit and update the bet button label
        app.betAmountStr = app.betAmountStr[:-1]


# * App Loop


def game_redrawAll(app):
    checkIfComplete(app)

    raiseButtonLabel = f"Bet: ${app.betAmountStr if app.betAmountStr else '0'}"

    drawTable(app)
    for i, player in enumerate(app.game.players):
        drawPlayerArea(app, i, player)
    drawCommunityCards(app)

    drawLabel(
        f"Pot: ${app.game.pot}",
        app.width / 2,
        app.height / 2 + 20,
        size=20,
        fill="white",
    )
    humanPlayer = app.game.players[0]

    toggleButtonText = "Hide" if app.showOtherPlayersCards else "Reveal"
    drawButton(app, toggleButtonText, app.toggleButtonLocation)
    drawButton(app, humanPlayer.checkOrCall, app.checkButtonLocation)
    drawButton(app, raiseButtonLabel, app.raiseButtonLocation)
    drawButton(app, "Fold", app.foldButtonLocation)


def checkIfComplete(app):
    if app.game.isFinished:
        setActiveScreen("restart")


# runApp(width=1200, height=1000) # we don't need this anymore because of main.py


# ---------------------------------------------------
# ---------------------------------------------------


def welcome_redrawAll(app):
    drawRect(0, 0, 1200, 1000, fill="black")

    drawLabel(
        "Welcome to Poker Trainer 112",
        app.width / 2,
        100,
        size=30,
        bold=True,
        fill="white",
    )

    # objective
    drawLabel("Objective:", 100, 150, size=20, bold=True, fill="white")
    drawLabel(
        "The goal is to win chips by having the best card combinations or betting",
        100,
        180,
        size=15,
        align="left",
        fill="white",
    )
    drawLabel(
        "other players out of the round", 100, 200, size=15, align="left", fill="white"
    )

    # basic Rules
    drawLabel("Basic Rules:", 100, 250, size=20, bold=True, fill="white")
    drawLabel(
        "Each player is dealt two cards. Additional community cards are released in stages.",
        100,
        280,
        size=15,
        align="left",
        fill="white",
    )
    drawLabel(
        "Your hand strength is decided by the combination of your two cards and the community cards.",
        100,
        300,
        size=15,
        align="left",
        fill="white",
    )
    drawLabel(
        "Within each round you can bet, check, call, or fold",
        100,
        320,
        size=15,
        align="left",
        fill="white",
    )

    # controls/flow
    drawLabel("Controls:", 100, 370, size=20, bold=True, fill="white")
    drawLabel(
        "Use the buttons on-screen to make your moves.",
        100,
        400,
        size=15,
        align="left",
        fill="white",
    )
    drawLabel(
        "Bots play instantaneously, so don't expect delays",
        100,
        420,
        size=15,
        align="left",
        fill="white",
    )

    drawLabel(
        "Press Enter to begin", app.width / 2, app.height - 50, size=20, fill="white"
    )


def welcome_onKeyPress(app, key):
    if key == "enter":
        setActiveScreen("game")

        setupGame(app)


# ---------------------------------------------------
# ---------------------------------------------------


def restart_redrawAll(app):
    drawLabel("Game Over", app.width / 2, app.height / 2 - 120, size=30, bold=True)
    drawLabel("You have run out of chips", app.width / 2, app.height / 2 - 60, size=20)
    drawLabel("Thank you for playing", app.width / 2, app.height / 2, size=20)
    drawButton(
        app, "Restart", (app.width / 2 - app.buttonWidth / 2, app.height / 2 + 60)
    )


def restart_onMousePress(app, mouseX, mouseY):
    if isWithinButton(
        app, mouseX, mouseY, (app.width / 2 - app.buttonWidth / 2, app.height / 2 + 50)
    ):
        setupGame(app)
        setActiveScreen("game")


# runAppWithScreens(initialScreen="welcome", width=1200, height=1000) # in main
