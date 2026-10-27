@endpoint:records.merge
Feature: Merge duplicate records
  When the same customer was entered twice, a person can merge the duplicates
  into the one record they keep. They choose which record each value comes
  from; everything attached to the duplicates moves over, and the duplicates
  are retired so links to them can still be followed.

  Background:
    Given Alice can view and change customers
    And a customer "Acme" with:
      | email | info@acme.test |
    And a customer "Acme dup" with:
      | email | billing@acme.test |

  Scenario: The kept record stays and the duplicates are retired into it
    Given a customer "Acme copy"
    When Alice merges "Acme dup" and "Acme copy" into "Acme"
    Then it succeeds
    And "Acme" is not deleted
    And "Acme dup" is merged into "Acme"
    And "Acme copy" is merged into "Acme"
    And Alice is taken to "Acme"

  Scenario: Values can be taken from any of the merged records
    When Alice merges "Acme dup" into "Acme", taking:
      | email | Acme dup |
    Then it succeeds
    And "Acme" has email "billing@acme.test"
    And "Acme" has name "Acme"

  Scenario: Values that are not picked keep what the kept record had
    When Alice merges "Acme dup" into "Acme"
    Then it succeeds
    And "Acme" has email "info@acme.test"

  Scenario: The record to keep need not be the one the merge was started from
    When Alice, on the page of "Acme dup", merges "Acme dup" into "Acme"
    Then it succeeds
    And "Acme" is not deleted
    And "Acme dup" is merged into "Acme"

  Scenario: Notes on a duplicate move to the kept record
    Given a note "Called about renewal" was left on "Acme dup"
    When Alice merges "Acme dup" into "Acme"
    Then the activity of "Acme" is "Called about renewal"

  Scenario: Notes elsewhere that mention a duplicate now mention the kept record
    Given a topic "Renewals"
    And a note "Renewal call" was left on "Renewals" about "Acme dup"
    When Alice merges "Acme dup" into "Acme"
    Then the note "Renewal call" is about "Acme"

  Scenario: Links to external systems move to the kept record
    Given "Acme dup" is linked to "42" in the "billing" system
    When Alice merges "Acme dup" into "Acme"
    Then "42" in the "billing" system is linked to "Acme"

  Scenario: Records merged into a duplicate earlier now point at the kept record
    Given a customer "Acme old"
    And "Acme old" was merged into "Acme dup"
    When Alice merges "Acme dup" into "Acme"
    Then "Acme old" is merged into "Acme"

  Scenario: A merge is recorded on the kept record and on each duplicate
    When Alice merges "Acme dup" into "Acme"
    Then the latest change to "Acme" is a merge
    And the latest change to "Acme" is labelled "Merged 1 record(s) into Acme"
    And the latest change to "Acme dup" is labelled "Merged into Acme"

  Scenario: Records that belong to a duplicate move to the kept record
    Given a ticket "Printer broken" with:
      | customer | Acme dup |
    When Alice merges "Acme dup" into "Acme"
    Then it succeeds
    And "Printer broken" has customer "Acme"

  Scenario: A duplicate still referenced in a way that cannot be moved cannot be merged
    Given a ticket "Printer broken"
    And "Acme dup" is a watcher of "Printer broken"
    When Alice merges "Acme dup" into "Acme"
    Then it is rejected with "still referenced by"
    And "Acme dup" is not deleted

  Scenario: A merge the record type's own checks refuse changes nothing
    Given customers refuse to be saved with "Customers are frozen"
    When Alice merges "Acme dup" into "Acme"
    Then it is rejected with "Customers are frozen"
    And "Acme dup" is not deleted

 
  Scenario: A merge without any duplicates is refused
    When Alice merges nothing into "Acme"
    Then it is rejected with "No objects to merge"
    And the change log of "Acme" has 0 entries

 
  Scenario: Records of different types cannot be merged
    Given Alice can view topics
    And a topic "Acme support"
    When Alice merges "Acme support" into "Acme"
    Then it is rejected with "Cannot merge"
    And "Acme support" is not deleted
    And the change log of "Acme" has 0 entries

  Scenario: Merging needs the change permission
    Given Bob can view customers
    When Bob merges "Acme dup" into "Acme"
    Then it is forbidden
    And "Acme dup" is not deleted
