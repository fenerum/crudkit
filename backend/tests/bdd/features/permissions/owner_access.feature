Feature: People may work on the records they created
  A record type can let every signed-in person view and change the records
  they created themselves, without being given the view or change permission.
  Everybody else's records stay out of reach, and deleting still needs the
  delete permission.

  Background:
    Given people may view and change the customers they created without a permission
    And Bob is a user without any permissions
    And Bob owns a customer "Bobco"
    And a customer "Acme"

  Scenario: The list holds only the records the person created
    When Bob looks at the list of customers
    Then the list holds only "Bobco"

  Scenario: A person can open and change a record they created
    When Bob looks at "Bobco"
    Then it succeeds
    When Bob changes the status of "Bobco" to "churned"
    Then it succeeds
    And "Bobco" has status "churned"

  Scenario: Records created by someone else stay out of reach
    When Bob looks at "Acme"
    Then it is not found
    When Bob changes the status of "Acme" to "churned"
    Then it is not found

  Scenario Outline: Owning records does not let a person add or delete them
    When Bob <does>
    Then it is forbidden

    Examples:
      | does                         |
      | creates a customer "Globex"  |
      | deletes "Bobco"              |

  Scenario: With the view permission, a person sees everybody's records again
    Given Bob can view customers
    When Bob looks at the list of customers
    Then the list holds "Acme" and "Bobco"
