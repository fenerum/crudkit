@type:AGT
Feature: Setting up an agent
  An agent is a saved instruction the assistant carries out in the background
  on one record type. CrudKit checks that an agent can actually work before it
  is saved, and makes sure nobody borrows someone else's permissions through one.

  Background:
    Given Alice can add agents

  Scenario Outline: An agent that cannot work is refused
    When Alice sets up an agent "Checker" with:
      | record type  | <type>     |
      | trigger      | <trigger>  |
      | schedule     | <schedule> |
      | watch fields | <watch>    |
    Then it is rejected with "<message>"

    Examples:
      | type                | trigger        | schedule | watch  | message                                    |
      | XYZ                 | manual         |          |        | Unknown record type                        |
      | assistant proposals | manual         |          |        | Agents can't work on assistant proposals   |
      | customers           | schedule       |          |        | Set a schedule exactly when the trigger is |
      | customers           | manual         | daily    |        | Set a schedule exactly when the trigger is |
      | customers           | record changed |          | colour | Not fields of customer                     |

  Scenario Outline: A sensible agent is saved and runs as the person who made it
    When Alice sets up an agent "Checker" with:
      | record type  | <type>     |
      | trigger      | <trigger>  |
      | schedule     | <schedule> |
      | watch fields | <watch>    |
    Then it succeeds
    And the agent "Checker" runs as Alice

    Examples:
      | type      | trigger        | schedule | watch         |
      | customers | manual         |          |               |
      | customers | schedule       | weekly   |               |
      | customers | record changed |          | status, email |
      | tickets   | record changed |          | watchers      |

  Scenario: An agent's saved view must list the record type it works on
    Given Alice has a saved view "Open tickets" listing tickets
    When Alice sets up an agent "Checker" with:
      | record type | customers    |
      | saved view  | Open tickets |
    Then it is rejected with "Pick a saved view of customers"

  Scenario: Only a superuser can make a new agent run as someone else
    Given Bob is a user without any permissions
    When Alice sets up an agent "Checker" with:
      | runs as | Bob |
    Then it is rejected with "Only superusers can make an agent run as another user"

  Scenario: The owner cannot switch an agent to run as someone else
    Given Bob is a user without any permissions
    And Alice has an agent "Fixer" that runs on customers when started by hand
    When Alice makes the agent "Fixer" run as Bob
    Then it is rejected with "Only superusers can make an agent run as another user"
    And the agent "Fixer" runs as Alice

  Scenario: A superuser can make an agent run as someone else
    Given Carol is a superuser
    And Bob is a user without any permissions
    And Alice has an agent "Fixer" that runs on customers when started by hand
    When Carol makes the agent "Fixer" run as Bob
    Then it succeeds
    And the agent "Fixer" runs as Bob

  Scenario: The owner cannot change what an agent running as someone else does
    Given Bob is a user without any permissions
    And Alice has an agent "Fixer" that runs on customers when started by hand
    And the agent "Fixer" was set to run as Bob by a superuser
    When Alice changes the instructions of "Fixer" to "Delete every customer."
    Then it is rejected with "Only superusers can change an agent that runs as another user (instructions)"

  Scenario: The owner can still turn off an agent that runs as someone else
    Given Bob is a user without any permissions
    And Alice has an agent "Fixer" that runs on customers when started by hand
    And the agent "Fixer" was set to run as Bob by a superuser
    When Alice turns the agent "Fixer" off
    Then it succeeds
    And the agent "Fixer" is turned off

  Scenario Outline: An agent and its runs are visible to their owner and to superusers only
    Given Bob has permission to view agents and agent runs
    And Carol is a superuser
    And a customer "Acme"
    And Alice has an agent "Fixer" that runs on customers when started by hand
    And the agent "Fixer" has already worked on "Acme"
    When <person> looks at the list of agents
    Then the list holds <agents>
    When <person> looks at the list of agent runs
    Then the list holds <runs>

    Examples:
      | person | agents  | runs            |
      | Alice  | "Fixer" | "Fixer on Acme" |
      | Bob    | nothing | nothing         |
      | Carol  | "Fixer" | "Fixer on Acme" |
