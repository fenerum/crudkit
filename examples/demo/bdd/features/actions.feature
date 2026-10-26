Feature: Actions
  A record type can offer its own actions, like marking a reading finished,
  from the actions menu. Each one asks before it runs, and the menu on a list
  only offers what applies to the list.

  Background:
    Given Alice is signed in
    And a reading "Weekend read"

  Scenario: Running an action from a record's menu
    When Alice runs "Mark finished" on "Weekend read" and confirms "Are you sure you want to mark finished?"
    Then she is told "Weekend read marked finished"
    When she reloads the page
    Then its status is "Finished"

  Scenario: Declining the confirmation leaves the record as it was
    When Alice runs "Mark finished" on "Weekend read" but declines "Are you sure you want to mark finished?"
    And she reloads the page
    Then its status is "To read"

  Scenario: A list's menu only offers what applies to the list
    When Alice opens the actions menu of the readings list
    Then the menu offers "Edit view"
    But the menu does not offer "Mark finished"
