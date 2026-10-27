@transactional
Feature: Scheduled agents
  A scheduled agent works through its records hourly, daily or weekly, so
  routine checks happen without anyone clicking. A scheduler looks every few
  minutes for agents that are due.

  Background:
    Given Alice can view and change customers
    And a customer "Acme"
    And a customer "Beta"

  Scenario Outline: A scheduled agent runs again once its interval has passed
    Given Alice has an agent "Sweeper" that runs <schedule> on customers
    And the agent "Sweeper" last ran on its schedule <ago> ago
    When the scheduler checks for due agents
    Then the scheduler started <runs>

    Examples:
      | schedule | ago        | runs    |
      | hourly   | 61 minutes | 2 runs  |
      | hourly   | 59 minutes | no runs |
      | daily    | 25 hours   | 2 runs  |
      | daily    | 23 hours   | no runs |
      | weekly   | 8 days     | 2 runs  |
      | weekly   | 6 days     | no runs |

  Scenario: A new scheduled agent runs at the first check
    Given Alice has an agent "Sweeper" that runs daily on customers
    When the scheduler checks for due agents
    Then the scheduler started 2 runs
    And the agent "Sweeper" ran on "Acme"
    And the agent "Sweeper" ran on "Beta"
    And the agent was asked to work on "Acme", which is due on the agent's schedule

  Scenario: A scheduled agent is started once however often the scheduler checks
    Given Alice has an agent "Sweeper" that runs daily on customers
    When the scheduler checks for due agents
    And the scheduler checks for due agents again
    Then the scheduler started no runs
    And the agent "Sweeper" ran twice

  Scenario: A scheduled run works on at most the agent's number of records per run
    Given a customer "Gamma"
    And Alice has an agent "Sweeper" that runs daily on customers
    And the agent "Sweeper" works on at most 2 records per run
    When the scheduler checks for due agents
    Then the scheduler started 2 runs

  Scenario: A scheduled run starts no more runs than are left for the day
    Given Alice has an agent "Sweeper" that runs daily on customers
    And the agent "Sweeper" may run at most 3 times a day
    And the agent "Sweeper" already ran 2 times today
    When the scheduler checks for due agents
    Then the scheduler started 1 run

  Scenario: A turned-off scheduled agent does not run
    Given Alice has an agent "Sweeper" that runs daily on customers
    And the agent "Sweeper" is turned off
    When the scheduler checks for due agents
    Then the scheduler started no runs

  Scenario: A broken scheduled agent does not hold up the others
    Given Alice has an agent "Broken" that runs daily on customers
    And the record type of the agent "Broken" no longer exists
    And Alice has an agent "Sweeper" that runs daily on customers
    When the scheduler checks for due agents
    Then the scheduler started 2 runs
    And the agent "Sweeper" ran twice
    And the agent "Broken" did not run
