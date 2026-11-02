Feature: Changing many records at once
  People select records in a list and change a field or delete them all in
  one go, instead of opening each one. The whole change can be undone from
  the notification it leaves.

  Background:
    Given Alice is signed in
    And a reading "Pile one" with status "To read"
    And a reading "Pile two" with status "To read"

  Scenario: A field is set on every selected record
    When Alice selects "Pile one" and "Pile two" in the readings list
    And she edits the status of the selection
    And she picks "Finished" as the status
    And she sets it on the selection
    Then she is told "2 readings updated successfully"
    When she opens "Pile two"
    Then its status is "Finished"

  Scenario: Changing many records is undone in one step
    When Alice selects "Pile one" and "Pile two" in the readings list
    And she edits the status of the selection
    And she picks "Finished" as the status
    And she sets it on the selection
    And she undoes it from the notification
    And she opens "Pile one"
    Then its status is "To read"

  Scenario: Several records are deleted at once
    When Alice selects "Pile one" and "Pile two" in the readings list
    And she deletes the selection
    Then she is told "2 readings deleted successfully"
    And the list is empty
