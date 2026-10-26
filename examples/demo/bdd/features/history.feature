Feature: History and undo
  Every change is kept in the record's history, so a mistake can be put right
  with one click: an edit can be reverted, a delete undone from the
  notification, and a deleted record restored from its page.

  Background:
    Given Alice is signed in
    And a reading "Diary"

  Scenario: An edit can be reverted from the history
    Given Alice renamed "Diary" to "Diary, edited"
    When she reverts her latest change in the history of "Diary"
    Then the history shows the revert
    When she opens "Diary"
    Then its name is "Diary"

  Scenario: Deleting says the record can be restored
    When Alice is about to delete "Diary"
    Then she is told "You can restore it from History."

  Scenario: A delete can be undone from the notification
    When Alice deletes "Diary"
    And she undoes it from the notification
    Then she is on the page of "Diary"
    And "Diary" is not marked as deleted

  Scenario: A deleted record can be restored from its page
    Given Alice deleted "Diary"
    When she restores "Diary" from its page
    Then "Diary" is not marked as deleted
