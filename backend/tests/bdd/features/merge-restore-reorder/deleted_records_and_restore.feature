@endpoint:records.restore
Feature: Deleted records and bringing them back
  Deleting a record only hides it, so nothing is lost. Deleted records can be
  listed on their own, and anyone who may change a record can restore it,
  unless it was merged into another one.

  Background:
    Given Alice can view, change and delete customers
    And a customer "Acme"
    And a customer "Globex"

  Scenario: Deleted records can be listed on their own
    Given Alice deleted "Acme"
    When Alice looks at the deleted customers
    Then the list holds only "Acme"

  Scenario: Restoring a deleted record brings it back
    Given Alice deleted "Acme"
    When Alice restores "Acme"
    Then it succeeds
    And "Acme" is not deleted
    And the latest change to "Acme" is a restore

  Scenario: A restore can be undone like any other change
    Given Alice deleted "Acme"
    And Alice restored "Acme"
    When Alice undoes that change
    Then it succeeds
    And "Acme" is deleted

  Scenario: A record that is not deleted cannot be restored
    When Alice restores "Acme"
    Then it is rejected with "is not deleted"

  Scenario: A record merged into another one cannot be restored
    Given "Globex" was merged into "Acme"
    When Alice restores "Globex"
    Then it is rejected with "cannot be restored"
    And "Globex" is merged into "Acme"

  Scenario: Restoring needs the change permission
    Given Bob can view customers
    And Alice deleted "Acme"
    When Bob restores "Acme"
    Then it is forbidden
    And "Acme" is deleted
