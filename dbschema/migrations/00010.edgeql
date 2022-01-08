CREATE MIGRATION m1g375hf7gkdrwmjyjm5gtnjgtkqik2xnotfxvnefja67ebqy4z7ka
    ONTO m1rar3irt5aziikd5yx2kltht6se5idl4huiwngsi4ftvskigmi5cq
{
  ALTER TYPE default::User {
      ALTER PROPERTY tag {
          RENAME TO full_tag;
      };
  };
};
