Feature: Notes
  Anyone can leave a note on a record's feed, so what was said about it stays
  with the record instead of in someone's inbox.

  Background:
    Given Alice is signed in
    And an author "Correspondent"

  Scenario: A posted note appears in the feed
    When Alice posts the note "Met at the book fair" on "Correspondent"
    Then she is told "Note posted"
    And the feed shows "Met at the book fair"

  Scenario: A posted note is still there after reloading
    When Alice posts the note "Met at the book fair" on "Correspondent"
    And she reloads the page
    Then the feed shows "Met at the book fair"
