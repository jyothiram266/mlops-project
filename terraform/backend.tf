# =============================================================================
# Terraform — Remote Backend Configuration
# =============================================================================
# Uncomment and configure the S3 backend for team collaboration.
# You must first create the S3 bucket and DynamoDB table.
#
# Create the backend resources:
#   aws s3api create-bucket --bucket ml-platform-tfstate --region us-east-1
#   aws s3api put-bucket-versioning --bucket ml-platform-tfstate \
#     --versioning-configuration Status=Enabled
#   aws dynamodb create-table --table-name ml-platform-tflock \
#     --attribute-definitions AttributeName=LockID,AttributeType=S \
#     --key-schema AttributeName=LockID,KeyType=HASH \
#     --billing-mode PAY_PER_REQUEST
# =============================================================================

# terraform {
#   backend "s3" {
#     bucket         = "ml-platform-tfstate"
#     key            = "eks/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "ml-platform-tflock"
#     encrypt        = true
#   }
# }
