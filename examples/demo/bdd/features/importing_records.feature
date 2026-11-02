@page:/<segment>/import
Feature: Importing records from a spreadsheet
  A list kept elsewhere can be brought in from an Excel or CSV file. The
  columns are matched to fields and every row is checked before anything is
  saved, and the whole import can be undone in one go.

  Background:
    Given Alice is signed in

  Scenario: The list's actions menu offers importing
    When Alice opens the actions menu of the books list
    Then the menu offers "Import…"

  Scenario: Importing books whose author is given by name
    When Alice uploads a books sheet:
      | Title | Author            |
      | Dawn  | Octavia E. Butler |
      | Imago | Octavia E. Butler |
    Then she sees "2 new"
    And the column "Title" goes into the name
    When she imports it, confirming "Create 2 books?"
    Then she is on the books list
    And the books list holds "Dawn" and "Imago"

  Scenario: Rows that can't be imported are pointed out and nothing is saved
    When Alice uploads a books sheet:
      | Title | Author        |
      | Dawn  | Nobody at all |
    Then she sees "1 with errors" and "No author is called 'Nobody at all'"
    And she cannot import yet

  Scenario: An import can be undone from its notification
    When Alice uploads a books sheet:
      | Title | Author            |
      | Dawn  | Octavia E. Butler |
    And she imports it, confirming "Create 1 book?"
    And she undoes it from the notification
    Then the books list holds nothing of hers
