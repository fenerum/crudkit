Feature: Assistant
  The assistant sidebar is a chat about whatever is on screen: it knows which
  list or record is open and what is selected, and the conversation stays put
  while moving around the app.

  Background:
    Given Alice is signed in

  Scenario: The assistant opens and closes with the keyboard
    Given Alice is on the books list
    When she toggles the assistant with the keyboard
    Then the assistant is ready
    When she toggles the assistant with the keyboard
    Then the assistant is closed

  Scenario: The assistant knows what is selected in a list
    Given Alice is on the books list
    And the assistant is open
    When she selects "Kindred" in the list
    Then the assistant is looking at the books list with 1 selected

  Scenario: The assistant follows to the record that is opened
    Given Alice is on the books list
    And the assistant is open
    When she opens "Kindred" from the list
    Then the assistant is looking at "Kindred"

  Scenario: The assistant answers a question
    Given Alice is on the books list
    And the assistant is open
    When she asks the assistant "Hello there"
    Then the assistant answers

  Scenario: The conversation survives reloading the page
    Given Alice is on the books list
    And the assistant is open
    When she asks the assistant "Hello there"
    And she reloads the page
    Then the assistant still shows "Hello there"
