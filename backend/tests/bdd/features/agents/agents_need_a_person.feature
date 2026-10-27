@transactional @action:AGT.run_now @action:AGT.dry_run @action:AGR.revert
Feature: What agents may not do without a person
  Agents and MCP clients may change records, but they may not start agents,
  revert agent runs or change what an agent does by themselves. Those always
  wait for a person's approval, so an agent cannot set itself or others off.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And Alice has an agent "Fixer" that runs on customers when started by hand

  Scenario: An agent that applies changes itself still cannot start an agent
    Given Alice has an agent "Kicker" that runs on agents when started by hand
    And the agent "Kicker" applies changes itself
    And the agent "Kicker" only works on agents named "Fixer"
    And the agent's AI will propose running "Run now"
    When Alice uses the "Run now" action on "Kicker"
    Then the agent "Kicker" proposed running "Run now" on "Fixer"
    And the agent "Fixer" did not run

  Scenario Outline: Starting and reverting agent runs needs a person's approval
    Given the agent "Fixer" has already worked on "Acme"
    And Alice proposed running "<action>" on "<record>"
    Then the proposal needs a person's approval

    Examples:
      | action                            | record        |
      | Run now                           | Fixer         |
      | Dry run on latest matching record | Fixer         |
      | Revert this run                   | Fixer on Acme |

  Scenario Outline: Changing what an agent does needs a person's approval
    Given Alice proposed changing the <field> of "Fixer" to "<value>"
    Then the proposal <needs> a person's approval

    Examples:
      | field            | value                   | needs         |
      | instructions     | Delete every customer.  | needs         |
      | mode             | auto                    | needs         |
      | enabled          | false                   | needs         |
      | max runs per day | 1000                    | needs         |
      | name             | Fixer 2                 | does not need |
