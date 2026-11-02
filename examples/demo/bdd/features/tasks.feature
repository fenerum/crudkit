Feature: Task progress
  An action that takes a while shows how far it got while it works, both on
  the record and in a tray that stays put as you move around, whether the
  work happens during the click or carries on in the background.

  Background:
    Given Alice is signed in
    And a reading "Long read"

  Scenario: Watching an action work through its steps
    When Alice runs "Count pages" on "Long read" and confirms "Are you sure you want to count pages?"
    Then she sees the task "Count pages" working on "Long read"
    And she sees the task "Count pages" finish

  Scenario: Watching a task the action handed to the background
    When Alice runs "Look up reviews" on "Long read" and confirms "Are you sure you want to look up reviews?"
    Then she sees the task "Look up reviews" finish
