Feature: Who may read and write each kind of record
  Every record type is guarded by four permissions: view, add, change and
  delete. Administrators hand them out per person, so people only see and
  touch what their job needs. Superusers may do everything.

  Background:
    Given a customer "Acme"

  Scenario Outline: Someone who is not signed in is asked to sign in
    When someone who is not signed in <looks>
    Then it requires signing in

    Examples:
      | looks                         |
      | looks at the list of customers |
      | looks at "Acme"               |

  Scenario: A person without any permissions cannot list records
    Given Bob is a user without any permissions
    When Bob looks at the list of customers
    Then it is forbidden

  Scenario: The view permission lets a person list and open records
    Given Bob can view customers
    When Bob looks at the list of customers
    Then the list holds "Acme"
    When Bob looks at "Acme"
    Then it succeeds

  Scenario Outline: The view permission alone does not let a person write
    Given Bob can view customers
    And a customer "Acme copy"
    And a topic "Sales"
    When Bob <writes>
    Then it is forbidden
    And "Acme" still has status "active"
    And "Acme" is not deleted

    Examples:
      | writes                                       |
      | creates a customer "Globex"                  |
      | changes the status of "Acme" to "churned"    |
      | deletes "Acme"                               |
      | merges "Acme copy" into "Acme"               |
      | uses the "Mark churned" action on "Acme"     |
      | restores "Acme"                              |

  Scenario: Reordering needs the change permission
    Given Bob can view topics
    And a topic "Sales"
    And a topic "Bugs"
    When Bob reorders the topics by sort order as "Bugs" and "Sales"
    Then it is forbidden
    And "Bugs" still has sort order "0"

  Scenario Outline: The change permission covers editing, merging and running actions
    Given Bob can view and change customers
    And a customer "Acme copy"
    When Bob <changes>
    Then it succeeds

    Examples:
      | changes                                    |
      | changes the status of "Acme" to "churned"  |
      | merges "Acme copy" into "Acme"             |
      | uses the "Mark churned" action on "Acme"   |

  Scenario: Adding records needs the add permission
    Given Bob can view and add customers
    When Bob creates a customer "Globex"
    Then it succeeds

  Scenario: Deleting needs the delete permission, not just the change permission
    Given Bob can view and change customers
    And Carol can view and delete customers
    When Bob deletes "Acme"
    Then it is forbidden
    When Carol deletes "Acme"
    Then it succeeds
    And "Acme" is deleted

  Scenario: Superusers may do everything without being given permissions
    Given Alice is a superuser
    When Alice changes the status of "Acme" to "churned"
    Then it succeeds
    And "Acme" has status "churned"
