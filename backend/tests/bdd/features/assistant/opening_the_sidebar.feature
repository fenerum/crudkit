@websocket:ws/assistant/ @websocket:ws/assistant/<type_id>/<pk>/ @transactional
Feature: Opening the assistant sidebar
  The assistant lives in a sidebar that stays connected while a person moves
  around the app. Only signed-in people get an answer, and opening it on a
  record never reveals a record the person may not see.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"

  Scenario: A signed-in person gets an assistant that is ready to chat
    When Alice opens the assistant
    Then the assistant is ready for Alice

  Scenario: The assistant answers nobody before they sign in
    When someone opens the assistant and talks to it without signing in
    Then the assistant answers with the error "Auth required." and hangs up

  Scenario: A bad sign-in token is refused
    When someone opens the assistant and signs in with a bad token
    Then the assistant answers with the error "Invalid token." and hangs up

  Scenario: Opening the assistant on a record puts that record on screen
    Given the assistant will reply "Acme is an active customer."
    When Alice opens the assistant on "Acme"
    And Alice asks the assistant "what is this?"
    Then the assistant sees "Open record: customer Acme."
    And the assistant answers "Acme is an active customer."

  Scenario: The assistant cannot be opened on a record the person may not see
    Given Bob can view tickets
    When Bob opens the assistant on "Acme"
    Then the assistant turns Bob away

  Scenario: The browser reports the screen, and the assistant sees it with each message
    Given a customer "Beta"
    And Alice is looking at the list of customers
    And the list shows "Acme and Beta"
    And Alice has selected "Beta"
    When Alice opens the assistant
    And Alice asks the assistant "what about the selected one?"
    Then the assistant sees "Selected rows (1): Beta."
    And the assistant sees "what about the selected one?"

  Scenario: An unknown kind of message is answered with an error
    When Alice opens the assistant
    And Alice sends the assistant a "dance" message
    Then Alice sees the error "Unknown message type 'dance'"

  Scenario: An empty message starts no turn
    When Alice opens the assistant
    And Alice sends the assistant an empty message
    Then the assistant does not start a turn
