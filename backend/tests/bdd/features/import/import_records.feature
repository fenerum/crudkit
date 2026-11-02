@endpoint:records.import
Feature: Import records from a spreadsheet
  People bring lists from elsewhere (a lead list, last year's customers) as an
  Excel or CSV file. The import checks every row the way a form would, shows
  what it is going to do, then saves every row or none, as one change that can
  be undone.

  Background:
    Given Alice can view, add and change customers
    And Alice can view topics
    And a topic "Sales"
    And customers can also be matched on email

  Scenario: Each row of the sheet becomes a new record
    When Alice imports a customers sheet:
      | name   | email           | status  |
      | Globex | info@globex.com | churned |
      | Initech| hi@initech.com  |         |
    Then it succeeds
    And the import created 2, updated 0, left 0 unchanged and skipped 0
    And "Globex" has status "churned"
    And "Initech" has status "active"

  Scenario: A CSV file can be imported too
    When Alice imports a customers sheet saved as CSV:
      | name   | email           |
      | Globex | info@globex.com |
    Then it succeeds
    And "Globex" has email "info@globex.com"

  Scenario: Columns are matched to fields by their name or label, ignoring case
    When Alice previews importing a customers sheet:
      | Name   | E-mail address  | Notes   |
      | Globex | info@globex.com | VIP     |
    Then the column "Name" is suggested for the name
    And the column "Notes" is not suggested for anything

  Scenario: A column can be put into a field whatever it is called
    Given Alice puts the column "Company" into the name
    When Alice imports a customers sheet:
      | Company |
      | Globex  |
    Then it succeeds
    And "Globex" has status "active"

  Scenario: A linked record can be given by its name
    When Alice imports a customers sheet:
      | name   | topic |
      | Globex | sales |
    Then it succeeds
    And "Globex" has topic "Sales"

  Scenario: A linked record can be given by its ID
    When Alice imports a customers sheet:
      | name   | topic           |
      | Globex | the ID of Sales |
    Then it succeeds
    And "Globex" has topic "Sales"

  Scenario: A linked record that doesn't exist stops the import
    When Alice imports a customers sheet:
      | name   | topic   |
      | Globex | Support |
    Then it is rejected
    And row 2 of the sheet is rejected with "No topic is called 'Support'"
    And nothing was imported

  Scenario: A name shared by several linked records must be given as an ID instead
    Given a topic "Sales" with sort order "2"
    When Alice imports a customers sheet:
      | name   | topic |
      | Globex | Sales |
    Then row 2 of the sheet is rejected with "More than one topic is called 'Sales'"

  Scenario: A choice can be given by its label
    When Alice imports a customers sheet:
      | name   | status  |
      | Globex | CHURNED |
    Then it succeeds
    And "Globex" has status "churned"

  Scenario: A value that isn't one of the choices names the choices
    When Alice imports a customers sheet:
      | name   | status |
      | Globex | gone   |
    Then row 2 of the sheet is rejected with "'gone' is not one of: Active, Churned"

  Scenario: A preview says what would happen and saves nothing
    When Alice previews importing a customers sheet:
      | name    |
      | Globex  |
      | Initech |
    Then it succeeds
    And the import created 2, updated 0, left 0 unchanged and skipped 0
    And nothing was imported

  Scenario: One bad row stops the whole import
    When Alice imports a customers sheet:
      | name    | email     |
      | Globex  | not-email |
      | Initech |           |
    Then it is rejected
    And row 2 of the sheet is rejected with "Enter a valid email address"
    And nothing was imported

  Scenario: Empty rows are left out
    When Alice imports a customers sheet:
      | name   |
      |        |
      | Globex |
    Then it succeeds
    And the import created 1, updated 0, left 0 unchanged and skipped 0

  Scenario: Records that match on a column are updated, the rest created
    Given a customer "Acme" with:
      | email | info@acme.test |
    When Alice imports a customers sheet, updating those that match on email:
      | name   | email           | status  |
      | Acme   | INFO@acme.test  | churned |
      | Globex | info@globex.com |         |
    Then it succeeds
    And the import created 1, updated 1, left 0 unchanged and skipped 0
    And "Acme" has status "churned"

  Scenario: Only updating leaves rows without a match out
    Given a customer "Acme" with:
      | email | info@acme.test |
    When Alice imports a customers sheet, only updating those that match on email:
      | name   | email           | status  |
      | Acme   | info@acme.test  | churned |
      | Globex | info@globex.com |         |
    Then it succeeds
    And the import created 0, updated 1, left 0 unchanged and skipped 1

  Scenario: Records that match can be skipped instead
    Given a customer "Acme" with:
      | email | info@acme.test |
    When Alice imports a customers sheet, skipping those that match on email:
      | name   | email          | status  |
      | Acme   | info@acme.test | churned |
    Then it succeeds
    And the import created 0, updated 0, left 0 unchanged and skipped 1
    And "Acme" still has status "active"

  Scenario: Records can be matched on their ID
    Given a customer "Acme"
    When Alice imports a customers sheet, updating those that match on id:
      | id             | status  |
      | the ID of Acme | churned |
    Then it succeeds
    And "Acme" has status "churned"

  Scenario: An empty cell never clears a value
    Given a customer "Acme" with:
      | email  | info@acme.test |
      | status | churned        |
    When Alice imports a customers sheet, updating those that match on email:
      | name | email          | status |
      | Acme | info@acme.test |        |
    Then it succeeds
    And "Acme" still has status "churned"

  Scenario: A row that changes nothing is not logged
    Given a customer "Acme" with:
      | email | info@acme.test |
    When Alice imports a customers sheet, updating those that match on email:
      | name | email          |
      | Acme | info@acme.test |
    Then the import created 0, updated 0, left 1 unchanged and skipped 0
    And the change log of "Acme" has 0 entries

  Scenario: Records can only be matched on their ID, unique fields and the fields set up for it
    When Alice imports a customers sheet, updating those that match on name:
      | name |
      | Acme |
    Then it is rejected with "Records can't be matched on 'name'; use one of id, email"

  Scenario: A row matching several records stops the import
    Given a customer "Acme" with:
      | email | info@acme.test |
    And a customer "Acme Ltd" with:
      | email | info@acme.test |
    When Alice imports a customers sheet, updating those that match on email:
      | name | email          |
      | Acme | info@acme.test |
    Then row 2 of the sheet is rejected with "More than one customer has email"

  Scenario: The same key twice in a sheet updates the record the first row created
    When Alice imports a customers sheet, updating those that match on email:
      | name   | email           | status  |
      | Globex | info@globex.com |         |
      | Globex | info@globex.com | churned |
    Then the import created 1, updated 1, left 0 unchanged and skipped 0
    And "Globex" has status "churned"

  Scenario: Importing needs permission to add records
    Given Bob can view and change customers
    When Bob imports a customers sheet:
      | name   |
      | Globex |
    Then it is forbidden

  Scenario: Updating existing records needs permission to change them
    Given Bob can view and add customers
    When Bob imports a customers sheet, updating those that match on email:
      | name   | email           |
      | Globex | info@globex.com |
    Then it is forbidden

  Scenario: Only records the person may change are updated
    Given people may only change the customers they are the owner of
    And a customer "Acme" with:
      | email | info@acme.test |
    When Alice imports a customers sheet, updating those that match on email:
      | name | email          | status  |
      | Acme | info@acme.test | churned |
    Then row 2 of the sheet is rejected with "You may not change Acme"
    And nothing was imported

  Scenario: A sheet with too many rows is refused
    Given sheets may hold at most 5 rows
    When Alice imports a customers sheet of 6 rows
    Then it is rejected with "The file has more than 5 rows"

  Scenario: Only Excel and CSV files can be imported
    When Alice imports a file "customers.txt"
    Then it is rejected with "Upload an Excel workbook (.xlsx) or a CSV file"

  Scenario: The import is one change, labelled with the file
    When Alice imports a customers sheet:
      | name    |
      | Globex  |
      | Initech |
    Then the latest change to "Globex" is labelled "Imported from customers.xlsx"
    And the app is told the change set of the latest change to "Initech"

  Scenario: Undoing the import removes every record it created
    Given Alice can delete customers
    And Alice imported a customers sheet:
      | name    |
      | Globex  |
      | Initech |
    When Alice undoes that change
    Then it succeeds
    And "Globex" is deleted
    And "Initech" is deleted

  Scenario: The import shows as a task while it runs
    When Alice imports a customers sheet:
      | name    |
      | Globex  |
      | Initech |
    Then Alice's task "Import customers.xlsx" has succeeded with 2 of 2 steps done

  Scenario: A refused import shows as a failed task
    When Alice imports a customers sheet:
      | name   | status |
      | Globex | gone   |
    Then Alice's task "Import customers.xlsx" has failed with "1 of 1 rows have errors; nothing was imported"

  Scenario: A preview leaves no task behind
    When Alice previews importing a customers sheet:
      | name   |
      | Globex |
    Then Alice has no tasks
