@type:ASP @type:AIC
Feature: Which proposals need a person's approval
  Background agents in "apply changes" mode and MCP clients may make some
  changes straight away, but anything touching approval-protected fields or
  actions waits for a person to confirm it. This keeps the AI context, the
  agents themselves and similar sensitive settings under human control.

  Background:
    Given Alice is a superuser
    And a customer "Acme" with status "active"
    And an AI context document "Tone of voice" saying "Plain and friendly."
    And a background agent "Triage" that works on customers

  Scenario Outline: Ordinary changes do not need approval
    Given Alice proposed <change>
    Then the proposal does not need a person's approval

    Examples:
      | change                                       |
      | changing the name of "Acme" to "Acme Inc"    |
      | creating a customer "Globex"                 |
      | running "Mark churned" on "Acme"             |
      | adding the note "Called them" to "Acme"      |
      | changing the name of "Triage" to "Sorting"   |

  Scenario Outline: Changes to protected fields and actions need approval
    Given Alice proposed <change>
    Then the proposal needs a person's approval

    Examples:
      | change                                                           |
      | changing the body of "Tone of voice" to "Shout at people."       |
      | changing the order of "Tone of voice" to "5"                     |
      | changing the instructions of "Triage" to "Delete everything."    |
      | running "Run now" on "Triage"                                    |
      | running "Dry run on latest matching record" on "Triage"          |

  Scenario: Undoing an ordinary change does not need approval
    Given Alice changed the status of "Acme" to "churned"
    And Alice proposed undoing that change
    Then the proposal does not need a person's approval

  Scenario: Undoing a change to a protected field needs approval
    Given Alice changed the body of "Tone of voice" to "Shout at people."
    And Alice proposed undoing that change
    Then the proposal needs a person's approval

  Scenario: A note never needs approval, even on a protected record
    Given Alice proposed adding the note "Reviewed" to "Tone of voice"
    Then the proposal does not need a person's approval
