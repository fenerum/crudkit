@endpoint:records.bulk
Feature: Change many records at once
  From a list, people pick several records and change a field, delete them or
  run an action on all of them in one go. Records they may not touch are
  skipped and named; the rest change together and can be undone in one step.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with status "active"
    And a customer "Beta" with status "active"
    And a customer "Gamma" with status "active"

  Scenario: A field is set on every chosen record
    When Alice sets the status of "Acme", "Beta" and "Gamma" to "churned" at once
    Then 3 records were changed
    And "Acme" has status "churned"
    And "Beta" has status "churned"
    And "Gamma" has status "churned"

  Scenario: Records that were not chosen are left alone
    When Alice sets the status of "Acme" and "Beta" to "churned" at once
    Then "Gamma" still has status "active"

  Scenario: The whole change is undone in one step
    Given Alice set the status of "Acme" and "Beta" to "churned" at once
    When Alice undoes that change
    Then it succeeds
    And "Acme" has status "active"
    And "Beta" has status "active"

  Scenario: A value that is not allowed is refused before anything changes
    When Alice sets the status of "Acme" and "Beta" to "frozen" at once
    Then it is rejected
    And "Acme" still has status "active"
    And "Beta" still has status "active"

  Scenario: Records the person may not change are skipped and named
    Given people may only change the customers they are the owner of
    And the owner of "Acme" is "Alice"
    When Alice sets the status of "Acme" and "Beta" to "churned" at once
    Then 1 record was changed
    And "Beta" was skipped because "You may not change it"
    And "Acme" has status "churned"
    And "Beta" still has status "active"

  Scenario: A record that fails its own checks is skipped and the rest still change
    Given only superusers may run "Mark churned" on customers
    When Alice uses the "Mark churned" action on "Acme" and "Beta" at once
    Then 0 records were changed
    And "Acme" was skipped because "You may not do that"

  Scenario: Someone who may not change the type cannot change any of them
    Given Bob can view customers
    When Bob sets the status of "Acme" and "Beta" to "churned" at once
    Then it is forbidden
    And "Acme" still has status "active"

  Scenario: Several records are deleted at once
    Given Alice can delete customers
    When Alice deletes "Acme" and "Beta" at once
    Then 2 records were changed
    And "Acme" is deleted
    And "Beta" is deleted
    And "Gamma" is not deleted

  Scenario: Deleting many needs the delete permission
    When Alice deletes "Acme" and "Beta" at once
    Then it is forbidden
    And "Acme" is not deleted

  Scenario: An action runs on every chosen record
    When Alice uses the "Mark churned" action on "Acme" and "Beta" at once
    Then 2 records were changed
    And "Acme" has status "churned"
    And "Beta" has status "churned"
    And "Gamma" still has status "active"

  Scenario: An action run on many records shows one progress bar
    Given customers have an action "Recount" that works through 3 steps
    When Alice uses the "Recount" action on "Acme", "Beta" and "Gamma" at once
    Then Alice has only the task "Recount"
    And Alice's task "Recount" has succeeded with 3 of 3 steps done

  Scenario: Only so many records can be changed at once
    When Alice sets the status of 501 customers to "churned" at once
    Then it is rejected with "At most 500 records"

  Scenario: Records of another type cannot be included
    Given a topic "Billing"
    When Alice sets the status of "Acme" and "Billing" to "churned" at once
    Then it is rejected with "Only customers can be changed here"

  Scenario: Only the changes the app offers can be made
    When Alice tries to "archive" "Acme" and "Beta" at once
    Then it is rejected with "Unknown operation"
