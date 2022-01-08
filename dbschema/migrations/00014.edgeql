CREATE MIGRATION m1mb7mchpne74zwj24xvgd44l6lnukjmlykjwn7gvt6worlednl7gq
    ONTO m1bwzxcy6yjqwsvoe5c22ukbujtzjsp24sdmxek5tku6nndxm5gb5q
{
  ALTER TYPE default::User {
      ALTER PROPERTY full_tag {
          USING ((.name ++ .discriminator));
      };
  };
};
