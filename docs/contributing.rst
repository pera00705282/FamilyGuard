Contributing
============

We welcome contributions from the community! Here's how you can help improve the Crypto Trading library.

Development Setup
----------------

1. Fork the repository on GitHub
2. Clone your fork locally:

   .. code-block:: bash

      git clone https://github.com/yourusername/crypto-trading.git
      cd crypto-trading
      pip install -e .[dev]

3. Create a new branch for your changes:

   .. code-block:: bash

      git checkout -b feature/your-feature-name

4. Install pre-commit hooks:

   .. code-block:: bash

      pre-commit install

Coding Standards
----------------

- Follow `PEP 8`_ style guide
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep lines under 100 characters
- Use absolute imports

.. _PEP 8: https://www.python.org/dev/peps/pep-0008/

Testing
-------

Run the test suite:

.. code-block:: bash

   pytest tests/ --cov=src --cov-report=term-missing

We aim for at least 80% test coverage. Write tests for new features and bug fixes.

Documentation
------------

- Update documentation when adding new features
- Follow the existing documentation style
- Build documentation locally to verify changes:

  .. code-block:: bash

     cd docs
     make html
     open _build/html/index.html

Pull Request Process
-------------------

1. Ensure all tests pass
2. Update the CHANGELOG.md with your changes
3. Submit a pull request with a clear description of the changes
4. Reference any related issues
5. Ensure all CI checks pass

Code Review
-----------

- All pull requests require at least one review
- Be respectful and constructive in code reviews
- Address all review comments before merging

Reporting Issues
---------------

When reporting issues, please include:

- Description of the problem
- Steps to reproduce
- Expected behavior
- Actual behavior
- Version information
- Any relevant logs or screenshots

Feature Requests
---------------

We welcome feature requests! Please:

1. Check if the feature already exists
2. Explain why this feature would be useful
3. Include any relevant use cases

License
-------

By contributing, you agree that your contributions will be licensed under the project's license.

Thank you for contributing to Crypto Trading!
