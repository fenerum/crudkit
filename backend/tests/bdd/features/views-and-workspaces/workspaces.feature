@type:WSP
Feature: Workspaces
  A workspace gathers saved views as tabs, in the order they were put in, so
  a team gets one place for its daily lists. Like views, workspaces are shared
  unless made private, and only the person who made one may change it.

  Background:
    Given Alice can view, add, change and delete workspaces
    And Alice can view views
    And Bob can view, change and delete workspaces
    And Alice saved a view "Churned" of customers
    And Alice saved a view "Active" of customers

  Scenario: A workspace keeps its views in the order they were given
    When Alice saves a workspace "Sales" with the views "Churned" and "Active"
    Then it succeeds
    And the workspace "Sales" has the tabs "Churned" and "Active" in order

  Scenario: A workspace can start out empty
    When Alice saves a workspace "Later" without any views
    Then it succeeds
    And the workspace "Later" has no tabs

  Scenario Outline: A workspace only holds saved views that exist
    When Alice saves a workspace "Sales" holding <content>
    Then it is rejected with "<message>"
    And there is no workspace "Sales"

    Examples:
      | content                     | message                 |
      | a customer                  | is not a View id        |
      | something that is not an id | is not a View id        |
      | a view that does not exist  | does not exist          |
      | something other than a list | Format                  |

  Scenario: Everyone sees shared workspaces and their own private ones
    Given Alice saved a workspace "Sales" with the view "Churned"
    And Alice saved a private workspace "Alice's desk"
    And Bob saved a private workspace "Bob's desk"
    When Bob lists the workspaces
    Then the workspaces listed are "Bob's desk" and "Sales"

  Scenario: Someone else's shared workspace cannot be changed
    Given Alice saved a workspace "Sales" with the view "Churned"
    When Bob changes the name of "Sales" to "Bob's sales"
    Then it is not found
    And "Sales" still has name "Sales"

  Scenario: Someone else's shared workspace cannot be deleted
    Given Alice saved a workspace "Sales" with the view "Churned"
    When Bob deletes "Sales"
    Then it is not found
    And "Sales" is not deleted

  Scenario: Workspaces can be found by name
    Given Alice saved a workspace "Sales" with the view "Churned"
    And Alice saved a workspace "Support" with the view "Active"
    When Alice searches the workspaces for "sal"
    Then the workspaces listed are "Sales"
