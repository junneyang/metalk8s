@post @ci @local @slow @bootstrap
Feature: Bootstrap
    Scenario: Re-run bootstrap
        Given the Kubernetes API is available
        When we run bootstrap a second time
        Then the Kubernetes API is available
