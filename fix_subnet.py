import re

with open('main.tf', 'r', encoding='utf-8') as f:
    content = f.read()

# Add a filter to data "aws_subnets" to prefer us-east-1a
new_subnet_data = """data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "availability-zone"
    values = ["us-east-1a", "us-east-1b"]
  }
}"""

content = re.sub(
    r'data "aws_subnets" "default" \{[^{}]*filter \{[^{}]*name\s*=\s*"vpc-id"[^{}]*values\s*=\s*\[data\.aws_vpc\.default\.id\][^{}]*\}[^{}]*\}',
    new_subnet_data,
    content,
    flags=re.MULTILINE
)

with open('main.tf', 'w', encoding='utf-8') as f:
    f.write(content)
