from setuptools import setup

setup(name='hookshub',
      version='1.0',
      description='A module for parsing and acting against JSON hooks',
      url='git@github.com:gisce/hookshub.git',
      author='Jaume Florez',
      author_email='jflorez@gisce.net',
      license='MIT',
      packages=[
          'hookshub', 'hookshub/hooks', 'hookshub/hooks/webhook_hooks/',
      ],
      zip_safe=False)
