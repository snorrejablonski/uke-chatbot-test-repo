# UKE Chatbot POC Lambda Code
Repository for Oslo Kommune UKE Chatbot POC containing integration code for connecting:
- Workplace by Facebook
- Boost.ai
- UIPath
- Watson Explorer

------
Continuous deployment through AWS CodePipeline based on docs: [https://docs.aws.amazon.com/lambda/latest/dg/build-pipeline.html](https://docs.aws.amazon.com/lambda/latest/dg/build-pipeline.html)

#### Remember to install any Python dependencies into repository folder before pushing lambda functions with new dependencies
Just run `pip install -r requirements.txt -t ./dependencies`  

#### To test AWS Lambda code locally: Install AWS SAM local
Instructions are found here: [https://github.com/thoeni/aws-sam-local](https://github.com/thoeni/aws-sam-local) 